"""Batch PBIX extraction, documentation and a local catalogue. No shell execution."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

from .catalog import build_catalog, read_metadata, validate_metadata, describe_html
from .extracted_report import parse_extracted_report
from .model_parser import parse_model
from .report_parser import parse_report
from .renderer import build_payload, render_html
from .linker import link


def resolve_tool(value):
    tool = shutil.which(value) if value else shutil.which('pbi-tools')
    if not tool and value and Path(value).is_file():
        tool = str(Path(value).resolve())
    if not tool:
        raise ValueError('pbi-tools Desktop was not found. Install the Windows Desktop edition from https://github.com/pbi-tools/pbi-tools/releases and pass --pbi-tools "C:\\Tools\\pbi-tools\\pbi-tools.exe". Power BI Desktop 64-bit must also be installed.')
    if Path(tool).suffix.lower() in {'.bat', '.cmd'}:
        raise ValueError('Supply the pbi-tools executable, not a shell wrapper (.bat/.cmd).')
    if 'pbi-tools.core' in Path(tool).name.lower():
        raise ValueError('PBIX extraction requires pbi-tools Desktop, not pbi-tools.core.')
    return str(Path(tool).resolve())


def extract_pbix(source, destination, tool, timeout, log):
    command = [tool, 'extract', str(source), '-extractFolder', str(destination), '-modelSerialization', 'Raw']
    with log.open('w', encoding='utf-8') as stream:
        try:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout, shell=False)
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f'Extraction timed out after {timeout}s; see {log.name}. Increase --extract-timeout if needed.') from exc
    if result.returncode:
        raise ValueError(f'pbi-tools exited with code {result.returncode}; see {log.name}. Check its compatibility with this PBIX/Power BI Desktop version.')


def load_extracted(folder, source, has_embedded_model):
    # Raw serialization is Model/database.json. Accept TMDL and BIM too for
    # extractors which already produce project-format definitions.
    models = [folder / 'Model' / 'database.json', folder / 'Model' / 'model.bim', folder / 'model.bim']
    model_path = next((p for p in models if p.is_file()), None)
    if model_path is None and (folder / 'Model' / 'model.tmdl').is_file():
        model_path = folder / 'Model'
    if model_path is None:
        candidates = list(folder.glob('*.SemanticModel'))
        if len(candidates) == 1:
            model_path = candidates[0]
    if has_embedded_model and model_path is None:
        raise ValueError('PBIX contains an embedded model but extraction produced no readable model definition')
    model = parse_model(model_path) if model_path else None
    report_root = folder / 'Report'
    if not report_root.exists():
        candidates = list(folder.glob('*.Report'))
        if len(candidates) == 1:
            report_root = candidates[0]
    if (report_root / 'definition' / 'pages').is_dir() or (report_root / 'pages').is_dir():
        report = parse_report(report_root)
        report['name'] = source.stem
    else:
        report = parse_extracted_report(report_root, source.stem)
    if model is None:
        report['warnings'].append(dict(severity='warning', category='External semantic model',
            message='No embedded semantic model was extracted. This is report-only documentation; remote model tables, measures and data sources are not available.'))
    return model, report


def output_name(source, root):
    relative = source.relative_to(root).as_posix()
    stem = re.sub(r'[^\w .-]', '_', source.stem, flags=re.UNICODE).strip(' .')[:100] or 'Report'
    digest = hashlib.sha256(relative.encode('utf-8')).hexdigest()[:12]
    return f'{stem}--{digest}.html'


def atomic_json(path, value):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, suffix='.tmp', delete=False) as stream:
        tmp = Path(stream.name)
        json.dump(value, stream, indent=2, ensure_ascii=False)
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def run_batch(input_path, output_dir=None, recursive=False, tool=None, timeout=600, extractor=None):
    source_root = Path(input_path).resolve()
    if source_root.is_file():
        if source_root.suffix.lower() != '.pbix':
            raise ValueError('Expected a .pbix file')
        sources, root = [source_root], source_root.parent
    elif source_root.is_dir():
        root = source_root
        sources = sorted((p for p in (root.rglob('*') if recursive else root.iterdir())
                          if p.is_file() and not p.is_symlink() and p.suffix.lower() == '.pbix'),
                         key=lambda p: p.relative_to(root).as_posix())
    else:
        raise ValueError(f'PBIX input not found: {source_root}')
    if not sources:
        raise ValueError('No PBIX files found. Use --recursive to include subfolders.')
    if timeout <= 0:
        raise ValueError('--extract-timeout must be greater than zero')
    executable = resolve_tool(tool) if extractor is None else tool
    extractor = extractor or extract_pbix
    output = Path(output_dir).resolve() if output_dir else root / 'documentation'
    output.mkdir(parents=True, exist_ok=True)
    home = output / 'pbi-home.html'
    if home.exists() and 'name="pbi-documentation-hub"' not in home.read_text(encoding='utf-8-sig'):
        raise ValueError('pbi-home.html already exists and is not a generated catalogue; choose another output folder')
    logs = output / 'pbix-logs'
    logs.mkdir(exist_ok=True)
    results = []
    for number, source in enumerate(sources, 1):
        name = output_name(source, root)
        target = output / name
        log = logs / (Path(name).stem + '.log')
        row = dict(source=str(source), filename=name, title=source.stem, status='failed',
                   previousHtmlRetained=target.exists(), log=str(log.relative_to(output)))
        print(f'[{number}/{len(sources)}] {source.relative_to(root)}', flush=True)
        try:
            metadata = read_metadata(target.read_text(encoding='utf-8-sig')) if target.exists() else None
            existing = describe_html(target.read_text(encoding='utf-8-sig'), name) if target.exists() else None
            if existing and existing.get('pbixSource') != str(source):
                raise ValueError('Existing HTML belongs to a different source; choose another output directory')
            if target.exists() and metadata is None:
                raise ValueError('Existing output is not a metadata-enabled generated document; refusing to overwrite it')
            metadata = validate_metadata(metadata or {})
            if not metadata['reportLocation']:
                metadata['reportLocation'] = str(source)
            with zipfile.ZipFile(source) as archive:
                has_model = any(n.replace('\\', '/').strip('/').casefold() == 'datamodel' for n in archive.namelist())
            with tempfile.TemporaryDirectory(prefix='pbi-doc-extract-') as temporary:
                work = Path(temporary)
                extracted = work / 'extracted'
                extractor(source, extracted, executable, timeout, log)
                model, report = load_extracted(extracted, source, has_model)
                linked = link(model, report) if model else None
                payload = build_payload(model, report, linked, source.stem)
                payload['documentation'] = metadata
                payload['pbixSource'] = str(source)
                # Write on the target filesystem, then replace in one operation.
                # A failed extraction/render never destroys a previous HTML.
                with tempfile.TemporaryDirectory(prefix='.pbi-stage-', dir=output) as stage:
                    rendered = render_html(payload, Path(stage) / name)
                    os.replace(rendered, target)
                warnings = [w['message'] for w in report['warnings']]
                row.update(status='generated', mode=payload['mode'], warnings=warnings,
                           previousHtmlRetained=False, pages=len(report['pages']))
                print(f'  Wrote {name} ({payload["mode"]})', flush=True)
        except Exception as exc:
            row['error'] = f'{type(exc).__name__}: {exc}'
            if log.exists():
                with log.open('a', encoding='utf-8') as stream:
                    stream.write('\nDocumentation failure: ' + row['error'] + '\n')
            print('  FAILED: ' + row['error'], flush=True)
        results.append(row)
    summary = dict(generatedAt=datetime.now(timezone.utc).isoformat(), input=str(source_root),
                   output=str(output), generated=sum(r['status'] == 'generated' for r in results),
                   failed=sum(r['status'] == 'failed' for r in results), files=results)
    atomic_json(output / 'pbix-batch-results.json', summary)
    build_catalog(output)
    print(f'Generated {summary["generated"]}; failed {summary["failed"]}. Open {home}', flush=True)
    return summary
