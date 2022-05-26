# -*- coding: utf-8 -*-
"""
Modules
=======

Modules enable logical resource separation.

You may control enabled modules by modifying ``ENABLED_MODULES`` config
variable.
"""
import logging

from flask_restx_patched import is_module_enabled, module_required  # NOQA


def init_app(app, force_enable=False, force_disable=None, **kwargs):
    from importlib import import_module

    # Import all models first for db.relationship to avoid model look up
    # error:
    #
    # sqlalchemy.exc.InvalidRequestError: When initializing mapper
    # mapped class AssetGroupSighting->asset_group_sighting, expression
    # 'Sighting' failed to locate a name ('Sighting'). If this is a
    # class name, consider adding this relationship() to the <class
    # 'app.modules.asset_groups.models.AssetGroupSighting'> class after
    # both dependent classes have been defined.
    if force_disable is None:
        force_disable = []

    if force_enable:
        import glob
        import os

        skip_module_names = [
            'ia_config_reader',
            'utils',
        ]

        module_path = os.path.join(app.config['PROJECT_ROOT'], 'app', 'modules')
        module_paths = glob.glob('{}/*'.format(module_path))
        module_names = []
        for module_path in module_paths:
            _, module_name_raw = os.path.split(module_path)
            module_name, _ = os.path.splitext(module_name_raw)
            if module_name.startswith('__'):
                continue
            if module_name not in skip_module_names:
                module_names.append(module_name)
    else:
        module_names = app.config['ENABLED_MODULES']

    module_names = sorted(module_names)
    for module_name in module_names:
        try:
            import_module(f'.{module_name}.models', package=__name__)
        except ModuleNotFoundError:
            # Some modules don't have models and that's ok
            pass

    for module_name in module_names:
        if module_name not in force_disable:
            if force_enable and module_name not in app.config['ENABLED_MODULES']:
                enable_str = ' (forced)'
            else:
                enable_str = ''
            logging.info(
                'Init module %r%s'
                % (
                    module_name,
                    enable_str,
                )
            )
            import_module('.%s' % module_name, package=__name__).init_app(app, **kwargs)
        else:
            logging.info('Skipped module {!r} (force disabled)'.format(module_name))
