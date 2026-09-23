"""Adapt pbi-tools' Report/sections tree to the generator's report contract.

This is an internal adapter, not a PBIR converter. Legacy/custom visual coverage
is best-effort and explicitly prevents automatic deletion recommendations.
"""
import json
from pathlib import Path
from .report_parser import _collect_aliases, _collect_field_refs, _collect_filters
from .page_references import attach_report_locations


def read_json(path, default=None):
    if not path.exists():
        return default
    for encoding in ('utf-8-sig', 'utf-16'):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except (ValueError, UnicodeError):
            continue
    raise ValueError(f'Unreadable extracted JSON: {path.name}')


def object_json(path, required=False):
    value = read_json(path, None if required else {})
    if not isinstance(value, dict):
        raise ValueError(f'Missing or invalid report object: {path.name}')
    return value


def decode_embedded(node):
    if isinstance(node, dict):
        result = {}
        for key, value in node.items():
            if key in {'config', 'query', 'filters', 'dataTransforms'} and isinstance(value, str):
                value = json.loads(value)
            result[key] = decode_embedded(value)
        return result
    if isinstance(node, list):
        return [decode_embedded(value) for value in node]
    return node


def refs(blob, context):
    aliases, fields = {}, []
    _collect_aliases(blob, aliases)
    _collect_field_refs(blob, aliases, fields, context=context)
    unique = {json.dumps(f, sort_keys=True): f for f in fields}
    return list(unique.values())


def element(folder, filename):
    value = object_json(folder / filename, required=True)
    for key in ('config', 'query', 'filters', 'dataTransforms'):
        part = folder / (key + '.json')
        if part.exists():
            value[key] = read_json(part)
    return decode_embedded(value)


def filters(blob, level, target):
    aliases = {}
    _collect_aliases(blob, aliases)
    return _collect_filters(blob.get('filters'), aliases, level, target)


def parse_extracted_report(folder, name):
    root = Path(folder)
    report = element(root, 'report.json')
    sections = root / 'sections'
    if not sections.is_dir():
        raise ValueError('Extracted report has no sections directory; report format is unsupported. Try saving as PBIP/PBIR.')
    config = report.get('config') or {}
    if not isinstance(config, dict):
        raise ValueError('Report config must be an object')
    pages = []
    page_ids = set()
    items = [(p, element(p, 'section.json')) for p in sorted(sections.iterdir()) if p.is_dir()]
    items.sort(key=lambda item: item[1].get('ordinal', 0))
    for index, (folder, page) in enumerate(items):
        pid = str(page.get('name') or folder.name)
        if pid in page_ids:
            raise ValueError(f'Duplicate extracted page identity: {pid}')
        page_ids.add(pid)
        label = str(page.get('displayName') or pid)
        pc = page.get('config') or {}
        if not isinstance(pc, dict):
            raise ValueError(f'Page config must be an object: {label}')
        page_filters = filters(page, 'page', label)
        visuals = []
        visual_dir = folder / 'visualContainers'
        visual_ids = set()
        for vp in sorted(visual_dir.iterdir()) if visual_dir.exists() else []:
            if not vp.is_dir():
                continue
            visual = element(vp, 'visualContainer.json')
            vc = visual.get('config') or {}
            if not isinstance(vc, dict):
                raise ValueError(f'Visual config must be an object: {vp.name}')
            single = vc.get('singleVisual') or vc.get('singleVisualGroup') or {}
            vid = str(vc.get('name') or vp.name)
            if vid in visual_ids:
                raise ValueError(f'Duplicate visual identity on page {label}: {vid}')
            visual_ids.add(vid)
            vtype = single.get('visualType') or ('group' if 'singleVisualGroup' in vc else 'unknown')
            layouts = vc.get('layouts') or []
            position = dict((layouts[0].get('position') or {}) if layouts else {})
            position.update({k: visual[k] for k in ('x', 'y', 'width', 'height') if k in visual})
            title = None
            for obj in (single.get('vcObjects') or single.get('objects') or {}).get('title', []):
                literal = obj.get('properties', {}).get('text', {}).get('expr', {}).get('Literal', {}).get('Value')
                if isinstance(literal, str):
                    title = literal.strip("'")
            vf = filters(visual, 'visual', f'{label} / {title or vtype}')
            page_filters.extend(vf)
            # Alias maps stay within each query/config blob instead of leaking
            # from one visual/query into another.
            fields = []
            for key, blob in visual.items():
                if isinstance(blob, (dict, list)):
                    fields.extend(refs(blob, 'visual ' + key))
            visuals.append(dict(id=vid, type=vtype, title=title,
                                hidden=bool(vc.get('isHidden', False)), fields=fields, filters=vf,
                                **{k: position.get(k) for k in ('x', 'y', 'width', 'height')}))
        pages.append(dict(id=pid, name=label, hidden=pc.get('visibility') in (1, 'HiddenInViewMode', 'hidden'),
                          isActive=index == config.get('activeSectionIndex', 0), width=page.get('width'),
                          height=page.get('height'), visuals=visuals, filters=page_filters,
                          otherFields=refs(page, 'page expression')))
    if not pages:
        raise ValueError('No report pages were extracted; refusing to produce an apparently complete report')
    bookmarks = []
    bookmark_dir = root / 'bookmarks'
    # pbi-tools splits bookmark state across nested JSON files. Retain all
    # references at report scope; do not invent a specific page attribution.
    for path in sorted(bookmark_dir.rglob('*.json')) if bookmark_dir.exists() else []:
        blob = decode_embedded(read_json(path))
        bookmarks.append(dict(name=str(path.relative_to(bookmark_dir)), fields=refs(blob, 'bookmark')))
    return attach_report_locations(dict(name=name, pages=pages, reportFilters=filters(report, 'report', '(entire report)'),
        otherFields=refs(report, 'report expression'), bookmarks=bookmarks, manifest=[], warnings=[{
            'severity': 'warning', 'category': 'PBIX extraction coverage',
            'message': 'PBIX report adapted from pbi-tools legacy layout. Custom visuals, runtime selections and bookmark page attribution may be incomplete; deletion recommendations require PBIR validation.'}]))
