"""Validate shapes at file boundaries before extraction traverses them."""
import json


def validate_report(value):
    if not isinstance(value, dict):
        raise ValueError('Expected a report JSON object')
    objects = {'visual', 'position', 'query', 'queryState', 'Expression', 'SourceRef',
               'Column', 'Measure', 'HierarchyLevel', 'Aggregation', 'objects'}
    def walk(node, parent=''):
        if isinstance(node, dict):
            for key, child in list(node.items()):
                if key in objects or (key == 'Hierarchy' and parent == 'Expression'):
                    if not isinstance(child, dict):
                        raise ValueError(f'{key} must be an object')
                if key in {'Entity', 'Source', 'Property', 'Level'} and not isinstance(child, str):
                    raise ValueError(f'{key} must be text')
                if key == 'Name' and 'Entity' in node and not isinstance(child, str):
                    raise ValueError('Alias Name must be text')
                if key == 'filterConfig':
                    if isinstance(child, str):
                        child = json.loads(child)
                        node[key] = child
                    if child is not None and not isinstance(child, (dict, list)):
                        raise ValueError('filterConfig must be an object or array')
                if key == 'filters' and parent == 'filterConfig':
                    if not isinstance(child, list) or not all(isinstance(f, dict) for f in child):
                        raise ValueError('filters must be an array of objects')
                walk(child, key)
        elif isinstance(node, list):
            for child in node:
                walk(child, parent)
    walk(value)
    return value


def validate_model(doc):
    if not isinstance(doc, dict) or not isinstance(doc.get('model', doc), dict):
        raise ValueError('Semantic model must be a JSON object')
    collections = {'tables', 'columns', 'measures', 'partitions', 'relationships', 'roles',
                   'tablePermissions', 'hierarchies', 'levels', 'expressions', 'calculationItems',
                   'annotations', 'extendedProperties', 'dataSources'}
    objects = {'source', 'calculationGroup', 'detailRowsDefinition', 'formatStringDefinition'}
    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in collections and (not isinstance(value, list) or not all(isinstance(v, dict) for v in value)):
                    raise ValueError(f'Model {key} must be an array of objects')
                if key in objects and value is not None and not isinstance(value, dict):
                    raise ValueError(f'Model {key} must be an object')
                if key in {'name', 'table', 'column', 'fromTable', 'toTable', 'fromColumn', 'toColumn'} and not isinstance(value, str):
                    raise ValueError(f'Model {key} must be text')
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(doc.get('model', doc))
