"""Live-connected reports: where a report with no embedded model gets its data.

A thin report (Analysis Services live connection, a published Power BI semantic
model, or a DirectQuery-for-datasets composite) carries no model of its own, but
it does say where the model lives. Static reads only; credentials are dropped.
"""
import json
import re
import zipfile

_SECRET = re.compile(r'^(password|pwd|user id|uid|access ?token|token|secret|application ?key)$', re.I)
_ASAZURE = re.compile(r'^asazure://', re.I)


def redact(connection_string):
    """Keep server and catalog identity; remove credential-like key/value pairs."""
    kept = []
    for part in str(connection_string or '').split(';'):
        key, sep, _ = part.partition('=')
        if part.strip() and sep and not _SECRET.match(key.strip()):
            kept.append(part.strip())
    return ';'.join(kept)


def _pairs(connection_string):
    out = {}
    for part in str(connection_string or '').split(';'):
        key, sep, value = part.partition('=')
        if sep:
            out[key.strip().lower()] = value.strip()
    return out


def describe(connection_string='', dataset_id='', report_id='', model_id=''):
    pairs = _pairs(connection_string)
    server = pairs.get('data source') or pairs.get('server') or ''
    database = pairs.get('initial catalog') or pairs.get('database') or ''
    if _ASAZURE.match(server):
        kind = 'Azure Analysis Services'
    elif server.lower().startswith(('powerbi://', 'pbiazure://')) or 'powerbi' in server.lower():
        kind = 'Power BI semantic model (XMLA endpoint)'
    elif server:
        kind = 'SQL Server Analysis Services'
    elif dataset_id or model_id:
        kind = 'Power BI semantic model (published dataset)'
    else:
        kind = 'External semantic model'
    return dict(kind=kind, server=server, database=database, datasetId=dataset_id,
                reportId=report_id, modelId=model_id, connectionString=redact(connection_string))


def from_pbix(source):
    """Read the PBIX `Connections` part. Returns a description dict or None."""
    try:
        with zipfile.ZipFile(source) as archive:
            raw = archive.read('Connections')
    except (KeyError, zipfile.BadZipFile, OSError):
        return None
    for encoding in ('utf-8-sig', 'utf-16'):
        try:
            data = json.loads(raw.decode(encoding))
            break
        except (ValueError, UnicodeError):
            data = None
    if not isinstance(data, dict):
        return None
    connections = [c for c in data.get('Connections') or [] if isinstance(c, dict)]
    artifacts = [a for a in data.get('RemoteArtifacts') or [] if isinstance(a, dict)]
    if not connections and not artifacts:
        return None
    first = connections[0] if connections else {}
    art = artifacts[0] if artifacts else {}
    return describe(first.get('ConnectionString', ''), art.get('DatasetId', ''), art.get('ReportId', ''),
                    first.get('PbiServiceModelId') or '')


def from_pbir(report_dir):
    """Read definition.pbir `byConnection`. Returns a description dict or None."""
    path = report_dir / 'definition.pbir'
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return None
    ref = (data.get('datasetReference') or {}).get('byConnection')
    if not isinstance(ref, dict):
        return None
    return describe(ref.get('connectionString', ''), model_id=str(ref.get('pbiServiceModelId') or ''))


def summary(live):
    if not live:
        return ''
    where = ' / '.join(x for x in (live.get('server'), live.get('database')) if x)
    return f"{live['kind']}{' — ' + where if where else ''}"
