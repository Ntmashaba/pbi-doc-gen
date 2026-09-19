"""Page-grained source-object inventory with original-code provenance."""
from __future__ import annotations
from .m_sources import Tracer, Value, materialize


def build_source_objects(model, report, columns):
    if not model:
        return []
    definitions = {}
    def add(name, code):
        if name in definitions and definitions[name] != code:
            definitions[name] = None  # Ambiguous names are not silently overwritten.
        else:
            definitions[name] = code
    for expression in model.get('expressions', []):
        if expression.get('kind', '').lower() == 'm':
            add(expression['name'], expression.get('expression') or '')
    for table in model['tables']:
        parts = table.get('partitions', [])
        if len(parts) == 1 and parts[0]['type'] == 'm':
            add(table['name'], parts[0].get('expression') or '')
    tracer = Tracer(definitions)
    rows = []
    report_name = report['name'] if report else 'Not supplied'
    for table in model['tables']:
        usages = [r for r in (columns or {}).get('tablePages', []) if r['table'] == table['name']]
        if not usages:
            usages = [dict(page='', pageId='', usage='Usage unknown', scope='Not assessed')]
        parts = table.get('partitions', []) or [dict(name='', type='none', expression='', source={})]
        for part in parts:
            code = part.get('expression') or ''
            original_m = code if part['type'] == 'm' else ''
            query_name = table['name'] if len(parts) == 1 else table['name'] + ' / ' + part['name']
            if part['type'] == 'm':
                extracted = materialize(tracer.trace(code))
            elif part['type'] == 'query':
                source = part.get('source', {})
                conn = dict(sourceType=source.get('sourceType') or 'SQL', server=source.get('server') or '',
                            database=source.get('database') or '', schema='')
                extracted = materialize(tracer.sql(Value(kind='connection', connections=[conn]), Value(kind='text', text=code)))
            elif part['type'] == 'entity':
                source = part.get('source', {})
                schema, obj = source.get('schema') or '', source.get('object') or ''
                if schema and obj.startswith(schema + '.'):
                    obj = obj[len(schema) + 1:]
                extracted = [dict(sourceType=source.get('sourceType') or 'Entity', server=source.get('server') or '',
                                  database=source.get('database') or '', schema=schema, object=obj,
                                  sql='', referencedM='', evidence='Entity partition metadata',
                                  notes=['Physical connection may require external metadata'], status='Partial' if obj else 'Unresolved')]
            else:
                extracted = [dict(sourceType='Calculated model table' if part['type'] == 'calculated' else 'No partition',
                                  server='', database='', schema='', object='', sql='', referencedM='',
                                  evidence='No direct external M/SQL source declared', notes=['Inspect upstream model-table dependencies'],
                                  status='Not applicable')]
            # One row per source identity in a partition, then per consuming page.
            # Multiple paths/statements keep their code and evidence on that row.
            unique = {}
            for item in extracted:
                key = tuple(item.get(k) or '' for k in ('sourceType', 'server', 'database', 'schema', 'object'))
                if key not in unique:
                    unique[key] = dict(item, sqlTexts=[item['sql']] if item['sql'] else [], evidenceItems=[item['evidence']])
                else:
                    old = unique[key]
                    old['notes'] = sorted(set(old['notes']) | set(item['notes']))
                    old['sqlTexts'] = list(dict.fromkeys(old['sqlTexts'] + ([item['sql']] if item['sql'] else [])))
                    old['evidenceItems'] = list(dict.fromkeys(old['evidenceItems'] + [item['evidence']]))
                    if item['status'] in {'Partial', 'Unresolved'}:
                        old['status'] = item['status']
            for item in unique.values():
                item['sql'] = '\n\n-- Next source statement --\n\n'.join(item.pop('sqlTexts'))
                item['evidence'] = '\n'.join(item.pop('evidenceItems'))
                for usage in usages:
                    rows.append(dict(item, report=report_name, page=usage['page'], pageId=usage['pageId'],
                                     pageScope=usage['scope'], pageUsage=usage['usage'], table=table['name'],
                                     partition=part['name'], queryName=query_name, originalM=original_m))
    return sorted(rows, key=lambda r: tuple(r[k] for k in ('table', 'partition', 'pageId', 'sourceType', 'server', 'database', 'schema', 'object')))
