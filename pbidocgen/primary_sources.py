"""External source identities, grouped by report page, without embedded code."""
from .m_sources import Tracer, materialize
from .source_objects import source_definitions


def build_primary_sources(model, report, source_objects):
    if not model:
        return dict(rows=[], unresolved=[])
    candidates = list(source_objects)
    reached = {name for row in source_objects for name in row.get('referencedQueries', [])}
    reached.update(name for row in source_objects for name in row.get('primaryQueries', []))
    # Shared queries with no traced model consumer also belong in the inventory.
    # Parameters alone are not external sources, and no page usage is invented.
    tracer = Tracer(source_definitions(model))
    report_name = report['name'] if report else 'Not supplied'
    for expression in model.get('expressions', []):
        name = expression['name']
        if expression.get('kind', '').lower() != 'm' or name in reached:
            continue
        value = tracer.named(name)
        if value.kind in {'text', 'literal'} and not value.connections and not value.objects:
            continue
        for item in materialize(value):
            candidates.append(dict(item, report=report_name, page='', pageId='',
                                   pageScope='No model consumer resolved', pageUsage='Not assessed',
                                   queryName=name, table=''))

    groups, unresolved = {}, {}
    for item in candidates:
        if item['status'] == 'Not applicable':
            continue
        origins = item.get('primaryQueries', [])
        if not origins or item['sourceType'] == 'Unknown':
            key = (item['report'], item['pageId'], item['pageScope'], item['queryName'])
            unresolved[key] = {k: item[k] for k in ('report', 'page', 'pageId', 'pageScope', 'queryName')}
            continue
        identity = ('report', 'page', 'pageId', 'pageScope', 'sourceType', 'server', 'database', 'schema', 'object')
        key = tuple(item.get(k, '') for k in identity)
        if key not in groups:
            groups[key] = dict(zip(identity, key), primaryQueries=set(), consumingQueries=set(),
                               tables=set(), pageUsage=set(), statuses=set())
        row = groups[key]
        row['primaryQueries'].update(origins)
        if item.get('table'):
            row['tables'].add(item['table'])
            row['consumingQueries'].add(item['queryName'])
        row['pageUsage'].add(item['pageUsage'])
        row['statuses'].add(item['status'])
    rows = []
    for row in groups.values():
        statuses = row.pop('statuses')
        row['status'] = 'Unresolved' if 'Unresolved' in statuses else 'Partial' if 'Partial' in statuses else 'Resolved'
        for key in ('primaryQueries', 'consumingQueries', 'tables', 'pageUsage'):
            row[key] = sorted(row[key])
        rows.append(row)
    return dict(rows=sorted(rows, key=lambda r: tuple(r[k] for k in ('report', 'pageId', 'pageScope', 'sourceType', 'server', 'database', 'schema', 'object'))),
                unresolved=[unresolved[k] for k in sorted(unresolved)])
