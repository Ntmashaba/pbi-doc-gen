"""Static M source tracing. Never evaluates M, SQL, credentials or network calls.

Supported: let bindings, literal parameters/concatenation, shared references,
connector calls, navigation records, native SQL and common table transforms.
Unsupported forms retain conservative dependencies and explicit diagnostics.
"""
from __future__ import annotations
import copy
import re
from dataclasses import dataclass, field
from .sql_sources import extract_sql_objects


@dataclass
class Token:
    value: str
    kind: str


def decode_m(value):
    value = value.replace('""', '"')
    def replace(match):
        result = ''
        for code in match[1].split(','):
            code = code.strip()
            if code in {'lf', 'cr', 'tab', '#'}:
                result += {'lf': '\n', 'cr': '\r', 'tab': '\t', '#': '#'}[code]
            elif re.fullmatch(r'[0-9a-fA-F]{4}|[0-9a-fA-F]{8}', code):
                point = int(code, 16)
                if 0xD800 <= point <= 0xDFFF:
                    raise ValueError('Isolated surrogate M escape')
                result += chr(point)
            else:
                raise ValueError('Unsupported M escape: #(' + code + ')')
        return result
    return re.sub(r'#\(([^)]+)\)', replace, value)


def tokenize(text):
    result, i = [], 0
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        if text.startswith('//', i):
            end = text.find('\n', i)
            i = len(text) if end < 0 else end
            continue
        if text.startswith('/*', i):
            depth, i = 1, i + 2
            while depth and i < len(text):
                if text.startswith('/*', i):
                    depth, i = depth + 1, i + 2
                elif text.startswith('*/', i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
            if depth:
                raise ValueError('Unterminated M comment')
            continue
        quoted_id = text.startswith('#"', i)
        if quoted_id or text[i] == '"':
            i += 2 if quoted_id else 1
            start, closed = i, False
            while i < len(text):
                if text[i] == '"':
                    if i + 1 < len(text) and text[i + 1] == '"':
                        i += 2
                        continue
                    closed = True
                    break
                i += 1
            if not closed:
                raise ValueError('Unterminated M string/identifier')
            result.append(Token(decode_m(text[start:i]), 'id' if quoted_id else 'string'))
            i += 1
            continue
        match = re.match(r'[^\W\d][\w.]*', text[i:], re.UNICODE)
        if match:
            result.append(Token(match[0], 'id'))
            i += len(match[0])
        else:
            result.append(Token(text[i], 'symbol'))
            i += 1
    return result


def pairs_for(ts):
    stack, pairs = [], {}
    for i, t in enumerate(ts):
        if t.kind != 'symbol':
            continue
        if t.value in '([{':
            stack.append(i)
        elif t.value in ')]}':
            if not stack or '([{'.index(ts[stack[-1]].value) != ')]}'.index(t.value):
                raise ValueError('Unbalanced M delimiters')
            pairs[stack.pop()] = i
    if stack:
        raise ValueError('Unbalanced M delimiters')
    return pairs


def top_positions(ts, delimiter):
    depth, lets = 0, 0
    for i, t in enumerate(ts):
        if t.kind == 'symbol' and t.value in '([{':
            depth += 1
        elif t.kind == 'symbol' and t.value in ')]}':
            depth -= 1
        elif not depth:
            if t.kind == 'id' and t.value == 'let':
                lets += 1
            elif t.kind == 'id' and t.value == 'in':
                lets -= 1
            elif not lets and t.value == delimiter and t.kind != 'string':
                yield i


def split(ts, delimiter=','):
    result, start = [], 0
    for i in top_positions(ts, delimiter):
        result.append(ts[start:i])
        start = i + 1
    result.append(ts[start:])
    return result


@dataclass
class Value:
    text: str | None = None
    kind: str = 'unknown'
    connections: list = field(default_factory=list)
    objects: list = field(default_factory=list)
    members: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    references: dict = field(default_factory=dict)


def union(values, issue=None):
    result = Value(kind='table')
    for value in values:
        result.connections += copy.deepcopy(value.connections)
        result.objects += copy.deepcopy(value.objects)
        result.issues += value.issues
        result.references.update(value.references)
    if issue:
        result.issues.append(issue)
    return result


CONNECTORS = {'Sql.Database': 'SQL Server', 'Sql.Databases': 'SQL Server',
              'Oracle.Database': 'Oracle', 'Teradata.Database': 'Teradata',
              'Odbc.DataSource': 'ODBC', 'Odbc.Query': 'ODBC'}
TRANSFORMS = {'Table.SelectRows', 'Table.SelectColumns', 'Table.RemoveColumns', 'Table.RenameColumns',
              'Table.TransformColumnTypes', 'Table.TransformColumns', 'Table.ReorderColumns',
              'Table.Sort', 'Table.Distinct', 'Table.Buffer', 'Table.FirstN', 'Table.LastN',
              'Table.Skip', 'Table.PromoteHeaders', 'Table.DemoteHeaders', 'Table.ReplaceValue',
              'Table.ExpandTableColumn', 'Table.ExpandRecordColumn', 'Table.RemoveRowsWithErrors',
              'Table.ReplaceErrorValues', 'Table.AddIndexColumn', 'Table.Unpivot', 'Table.UnpivotOtherColumns'}
COMBINES = {'Table.Combine', 'Table.Join', 'Table.NestedJoin'}


class Tracer:
    def __init__(self, definitions=None):
        self.definitions = definitions or {}
        self.cache, self.active = {}, set()

    def named(self, name):
        if name in self.cache:
            return copy.deepcopy(self.cache[name])
        if name in self.active:
            return Value(issues=['Cyclic shared-query reference: ' + name])
        if name in self.definitions and self.definitions[name] is None:
            return Value(issues=['Ambiguous shared-query name: ' + name])
        if name not in self.definitions:
            return Value(issues=['Unresolved M reference: ' + name])
        self.active.add(name)
        value = self.trace(self.definitions[name])
        self.active.remove(name)
        value.references[name] = self.definitions[name]
        self.cache[name] = copy.deepcopy(value)
        return value

    def trace(self, code):
        try:
            ts = tokenize(code)
            return self.evaluate(ts, self.named)
        except (ValueError, RecursionError) as exc:
            return Value(issues=['M extraction incomplete: ' + str(exc)])

    def evaluate(self, ts, resolve):
        if not ts:
            return Value(issues=['Empty M expression'])
        pairs = pairs_for(ts)
        if ts[0].kind == 'id' and ts[0].value == 'let':
            depth, lets, end = 0, 0, None
            for i, t in enumerate(ts):
                if t.kind == 'symbol' and t.value in '([{':
                    depth += 1
                elif t.kind == 'symbol' and t.value in ')]}':
                    depth -= 1
                elif not depth and t.kind == 'id':
                    if t.value == 'let':
                        lets += 1
                    elif t.value == 'in':
                        lets -= 1
                        if lets == 0:
                            end = i
                            break
            if end is None:
                return Value(issues=['M let expression has no matching in'])
            bindings, cache, active = {}, {}, set()
            for item in split(ts[1:end]):
                equals = list(top_positions(item, '='))
                if not equals or equals[0] != 1 or item[0].kind != 'id':
                    return Value(issues=['Unsupported M let binding'])
                if item[0].value in bindings:
                    return Value(issues=['Duplicate M let binding: ' + item[0].value])
                bindings[item[0].value] = item[2:]
            def local(name):
                if name not in bindings:
                    return resolve(name)
                if name in active:
                    return Value(issues=['Cyclic M let reference: ' + name])
                if name not in cache:
                    active.add(name)
                    cache[name] = self.evaluate(bindings[name], local)
                    active.remove(name)
                return copy.deepcopy(cache[name])
            return self.evaluate(ts[end + 1:], local)
        meta = list(top_positions(ts, 'meta'))
        if meta:
            return self.evaluate(ts[:meta[0]], resolve)
        concat = split(ts, '&')
        if len(concat) > 1:
            values = [self.evaluate(part, resolve) for part in concat]
            result = union(values)
            if all(v.kind == 'text' for v in values):
                result.kind, result.text = 'text', ''.join(v.text for v in values)
            else:
                result.issues.append('Dynamic M concatenation cannot be resolved')
            return result
        if len(ts) == 1:
            if ts[0].kind == 'string':
                return Value(text=ts[0].value, kind='text')
            if ts[0].kind == 'id':
                if ts[0].value in {'true', 'false', 'null'}:
                    return Value(text=ts[0].value, kind='literal')
                return resolve(ts[0].value)
            return Value(text=ts[0].value, kind='literal')
        if 0 in pairs and pairs[0] == len(ts) - 1:
            if ts[0].value == '(':
                return self.evaluate(ts[1:-1], resolve)
            if ts[0].value == '{':
                return union([self.evaluate(item, resolve) for item in split(ts[1:-1]) if item])
            if ts[0].value == '[':
                members = {}
                for item in split(ts[1:-1]):
                    eq = list(top_positions(item, '='))
                    if not item:
                        continue
                    if not eq or eq[0] != 1:
                        return Value(issues=['Row/record expression is not a static record'])
                    members[item[0].value] = self.evaluate(item[2:], resolve)
                result = union(members.values())
                result.kind, result.members = 'record', members
                return result
        # Peel navigation suffixes from a complete expression, not from a
        # regex match divorced from the connection that produced the value.
        ends = {end: start for start, end in pairs.items()}
        final = ends.get(len(ts) - 1)
        if final is not None and final > 0 and ts[final].value == '[':
            base = self.evaluate(ts[:final], resolve)
            if len(ts[final + 1:-1]) == 1:
                name = ts[final + 1].value
                if name in base.members:
                    member = copy.deepcopy(base.members[name])
                    member.references.update(base.references)
                    return member
                return base
        if final is not None and final > 0 and ts[final].value == '{':
            base = self.evaluate(ts[:final], resolve)
            record = self.evaluate(ts[final + 1:-1], resolve)
            return self.navigate(base, record)
        if ts[0].kind == 'id' and 1 in pairs and pairs[1] == len(ts) - 1:
            fn = ts[0].value
            arg_tokens = split(ts[2:-1])
            if fn in TRANSFORMS:
                first = self.evaluate(arg_tokens[0], resolve)
                # Simple row transformations preserve the input lineage. If an
                # argument calls code, inspect it conservatively for more input.
                extra = []
                for arg in arg_tokens[1:]:
                    if any(t.kind == 'id' and i + 1 < len(arg) and arg[i + 1].value == '(' for i, t in enumerate(arg)):
                        extra.append(self.evaluate(arg, resolve))
                return union([first] + extra)
            args = [self.evaluate(arg, resolve) for arg in arg_tokens if arg]
            if fn in CONNECTORS:
                return self.connector(fn, args)
            if fn == 'Value.NativeQuery':
                if len(args) < 2:
                    return Value(issues=['Value.NativeQuery lacks a target or SQL expression'])
                return self.sql(args[0], args[1])
            if fn in COMBINES:
                # Join key/column lists are scalar metadata, not data sources.
                if fn in {'Table.Join', 'Table.NestedJoin'} and len(args) >= 3:
                    return union([args[0], args[2]])
                return union(args)
            function = resolve(fn)
            if function.references or function.connections or function.objects:
                args.append(function)
            return union(args, 'Unsupported M function; dependencies may be incomplete: ' + fn)
        # Do not execute branches/lambdas. Retain known references as possible
        # sources and flag incompleteness, rather than choosing a branch.
        values = []
        for t in ts:
            if t.kind == 'id' and t.value not in {'each', 'if', 'then', 'else', 'true', 'false', 'null'}:
                candidate = resolve(t.value)
                if candidate.connections or candidate.objects:
                    values.append(candidate)
        return union(values, 'Unsupported/dynamic M expression; source coverage is incomplete')

    def connector(self, fn, args):
        result = union(args)
        result.objects, result.connections = [], []
        kind = CONNECTORS[fn]
        server = args[0].text if args and args[0].kind == 'text' else ''
        database = args[1].text if fn == 'Sql.Database' and len(args) > 1 and args[1].kind == 'text' else ''
        conn = dict(sourceType=kind, server=server or '', database=database or '', schema='')
        if not server:
            result.issues.append('Connection/server expression is unresolved')
        if fn.startswith('Odbc.'):
            parts = {}
            # Retain only source identity fields, never credentials.
            for match in re.finditer(r'(?:^|;)\s*([^=;]+)=\s*(\{(?:[^}]|}})*\}|[^;]*)', server or ''):
                parts[match[1].strip().lower()] = match[2].strip().strip('{}')
            driver = parts.get('driver', '').lower()
            conn['sourceType'] = 'Oracle' if 'oracle' in driver else 'Teradata' if 'teradata' in driver else 'SQL Server' if 'sql server' in driver else 'ODBC'
            conn['server'] = parts.get('server') or parts.get('dbq') or parts.get('data source') or ('dsn=' + parts['dsn'] if parts.get('dsn') else '')
            conn['database'] = parts.get('database') or parts.get('initial catalog') or ''
            if parts.get('dsn'):
                result.issues.append('ODBC DSN requires external configuration to resolve its physical connection')
            if not conn['server']:
                result.issues.append('ODBC connection identity is unresolved')
        if kind == 'Oracle' and server and '/' in server and not server.startswith('('):
            conn['database'] = server.rsplit('/', 1)[1]
        result.connections = [conn]
        result.kind = 'connection'
        opts_index = 2 if fn == 'Sql.Database' else 1
        if fn == 'Odbc.Query':
            return self.sql(result, args[1] if len(args) > 1 else Value())
        if len(args) > opts_index and 'Query' in args[opts_index].members:
            return self.sql(result, args[opts_index].members['Query'])
        return result

    def sql(self, target, query):
        result = union([target, query])
        result.objects = []
        if query.kind != 'text':
            result.issues.append('Native SQL text is dynamic or unavailable')
            for conn in target.connections or [dict(sourceType='Unknown', server='', database='', schema='')]:
                result.objects.append(dict(conn, object='', sql='', evidence='Unresolved native SQL', notes=['Native SQL text is dynamic or unavailable']))
            return result
        connections = list({tuple(sorted(c.items())): c for c in target.connections}.values())
        if len(connections) != 1:
            result.issues.append('Native SQL target connection is ambiguous or unresolved')
            conn = dict(sourceType='Unknown', server='', database='', schema='')
        else:
            conn = connections[0]
        objects, issues = extract_sql_objects(query.text)
        result.issues += issues
        for parts in objects:
            row = dict(conn, object=parts[-1], sql=query.text, evidence='Native SQL object: ' + '.'.join(parts), notes=[])
            if len(parts) == 2:
                row['database' if conn['sourceType'] == 'Teradata' else 'schema'] = parts[0]
            elif len(parts) == 3:
                row['database'], row['schema'] = parts[:2]
            elif len(parts) == 4 and conn['sourceType'] == 'SQL Server':
                row['server'], row['database'], row['schema'] = parts[:3]
                row['notes'].append('Four-part SQL server name may be a linked-server alias')
            elif len(parts) > 3:
                row['object'] = '.'.join(parts)
                row['notes'].append('Qualified object naming is not supported for this dialect')
            if '@' in row['object']:
                row['notes'].append('Object uses a database link; server is the entry connection, not a verified remote host')
            if len(parts) <= 2 and conn['sourceType'] != 'Teradata' and any('database context with USE' in issue for issue in issues):
                row['database'] = ''
                row['notes'].append('SQL USE overrides the connection database; inspect the original SQL')
            if len(parts) == 1:
                row['notes'].append('Unqualified SQL object; default schema/database not verified')
            result.objects.append(row)
        if not objects:
            result.objects.append(dict(conn, object='', sql=query.text, evidence='Native SQL', notes=['No physical source object resolved from this SQL']))
        elif issues:
            # Keep a distinct coverage row so known objects do not hide an
            # unsupported source elsewhere in the same statement.
            result.objects.append(dict(conn, object='', sql=query.text, evidence='SQL coverage gap', notes=issues))
        result.kind = 'table'
        return result

    def navigate(self, base, record):
        result = union([base, record])
        if record.kind != 'record' or not base.connections:
            result.issues.append('Navigation target or key is unresolved')
            return result
        fields = {k.lower(): v.text for k, v in record.members.items() if v.kind == 'text'}
        if len(fields) != len(record.members):
            result.issues.append('Navigation uses a nonliteral key')
            result.objects = [dict(c, object='', sql='', evidence='Unresolved navigation', notes=['Navigation uses a nonliteral key']) for c in base.connections]
            return result
        kind = (fields.get('kind') or '').lower()
        name = fields.get('item') or fields.get('name')
        result.connections, result.objects = [], []
        if len(base.connections) != 1:
            result.issues.append('Navigation has multiple possible connections')
            return result
        conn = dict(base.connections[0])
        if kind == 'database' or (conn['sourceType'] in {'SQL Server', 'Teradata'} and not conn['database'] and name and not fields.get('schema') and kind not in {'table', 'view'}):
            conn['database'] = name or ''
        elif kind == 'schema' or (fields.get('schema') and not name):
            namespace = fields.get('schema') or name or ''
            conn['database' if conn['sourceType'] == 'Teradata' else 'schema'] = namespace
        elif name:
            schema = fields.get('schema') or conn['schema']
            if conn['sourceType'] == 'Teradata':
                conn['database'] = schema or conn['database']
                schema = ''
            row = dict(conn, schema=schema, object=name, sql='', evidence='M navigation: ' + repr(fields), notes=[])
            if not schema and conn['sourceType'] in {'SQL Server', 'Oracle'}:
                row['notes'].append('Navigation schema is not supplied')
            result.objects.append(row)
        else:
            result.issues.append('Navigation has no identifiable object name')
        result.connections = [conn]
        result.kind = 'table' if result.objects else 'connection'
        return result


def materialize(value):
    rows = copy.deepcopy(value.objects)
    if rows and not any(not r.get('object') for r in rows) and any('Unsupported' in issue or 'Cyclic' in issue for issue in value.issues):
        rows.append(dict(sourceType='Unknown', server='', database='', schema='', object='', sql='', evidence='M coverage gap', notes=value.issues[:]))
    if not rows:
        for conn in value.connections or [dict(sourceType='Unknown', server='', database='', schema='')]:
            rows.append(dict(conn, object='', sql='', evidence='M expression', notes=['Source object unresolved']))
    for row in rows:
        notes = set(row.get('notes', [])) | set(value.issues)
        if not row.get('server'):
            notes.add('Server/connection unresolved')
        if not row.get('database'):
            notes.add('Database/service not supplied or unresolved')
        row['notes'] = sorted(notes)
        row['status'] = 'Unresolved' if not row['object'] else 'Partial' if notes else 'Resolved'
        row['referencedM'] = '\n\n'.join(f'// Referenced query: {name}\n{code}' for name, code in sorted(value.references.items()))
    return rows
