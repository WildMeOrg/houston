# -*- coding: utf-8 -*-
"""
Modules
=======

Modules enable logical resource separation.

You may control enabled modules by modifying ``ENABLED_MODULES`` config
variable.
"""
import logging


def init_app(app, **kwargs):
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
    for module_name in app.config['ENABLED_MODULES']:
        try:
            import_module(f'.{module_name}.models', package=__name__)
        except ModuleNotFoundError:
            # Some modules don't have models and that's ok
            pass

    for module_name in app.config['ENABLED_MODULES']:
        logging.debug('Init module %r' % (module_name,))
        import_module('.%s' % module_name, package=__name__).init_app(app, **kwargs)
