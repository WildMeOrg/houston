# -*- coding: utf-8 -*-
from app.extensions import db
from app.modules import is_module_enabled
from app.modules.fileuploads.models import FileUpload  # NOQA
from app.modules.site_settings.models import SiteSetting  # NOQA
from tasks.utils import app_context_task


@app_context_task(
    help={
        'key': 'Setting name, e.g. header_image',
        'filepath': '/path/to/local/file.foo',
    }
)
def set(context, key, filepath, public=True):
    fup = FileUpload.create_fileupload_from_path(filepath, copy=True)

    with db.session.begin():
        db.session.add(fup)
        setting = SiteSetting.set(key, fup.guid, public=public)
    print(repr(setting))


@app_context_task(
    help={
        'key': 'Setting name, e.g. header_image',
    }
)
def get(context, key):
    print(repr(SiteSetting.query.get(key)))


@app_context_task(
    help={
        'key': 'Setting name, e.g. header_image (note also supports configuration keys like site.name)',
    }
)
def get_value(context, key, default=None):

    if not default:
        val = SiteSetting.get_value(key)
    else:
        val = SiteSetting.get_value(key, default=default)
    print(repr(val))


@app_context_task()
def get_public_data(context, debug=False):

    if debug:
        breakpoint()

    if is_module_enabled('individuals'):
        from app.modules.individuals.models import Individual

        print(f'num_individuals: {Individual.query_search().count()}')

    if is_module_enabled('sightings'):
        from app.modules.sightings.models import Sighting

        print(f'num_sightings: {Sighting.query_search().count()}')

    if is_module_enabled('users'):
        from app.modules.users.models import User

        num_internal_users = User.query.filter(
            User.static_roles.op('&')(User.StaticRoles.INTERNAL.mask) > 1
        ).count()

        print(
            f'num_users: {User.query_search().count()} of which {num_internal_users} are internal'
        )

    if is_module_enabled('asset_groups'):
        from app.modules.asset_groups.models import (
            AssetGroupSighting,
            AssetGroupSightingStage,
        )

        num_pending_sightings = AssetGroupSighting.query.filter(
            AssetGroupSighting.stage != AssetGroupSightingStage.processed
        ).count()
        print(f'num_pending_sightings: {num_pending_sightings}')
