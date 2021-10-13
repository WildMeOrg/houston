#!/usr/bin/env python
# -*- coding: utf-8 -*-
from importlib import import_module
import pathlib

import pydot


def get_models():
    for models_py in pathlib.Path('app/modules/').glob('*/models.py'):
        module_path = str(models_py).replace('.py', '').replace('/', '.')
        module = import_module(module_path)
        for name in dir(module):
            # We want all the classes from models.py
            if not name.startswith('_') and name[0].upper() == name[0]:
                cls = getattr(module, name)
                if type(cls).__name__ == 'DefaultMeta':
                    yield cls


graph = pydot.Dot('models_graph', graph_type='graph', label='Houston Models')
relationships = []
for model in get_models():
    column_names = []
    for column in model.__table__.columns:
        foreign_key = ''
        column_names.append(column.name)
        if column.foreign_keys:
            foreign_key = list(column.foreign_keys)[0].target_fullname
            linked_class = foreign_key.split('.')[0]
            if not column.name.startswith(linked_class):
                column_names[-1] += f' ({linked_class})'
            linked_class = linked_class.replace('_', '').lower()
            relationships.append((model.__name__.lower(), linked_class))
    graph.add_node(
        pydot.Node(
            model.__name__.lower(),
            fontsize='10',
            label='{%s|%s}' % (model.__name__, '\n'.join(column_names)),
            shape='record',
        )
    )
for cls1, cls2 in relationships:
    graph.add_edge(pydot.Edge(cls1, cls2))
graph.write_png('./docs/models-graph.png')
print('Output in ./docs/models-graph.png')
