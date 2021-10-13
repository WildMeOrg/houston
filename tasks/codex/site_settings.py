# -*- coding: utf-8 -*-
from app.extensions import db
from app.modules.fileuploads.models import FileUpload
from app.modules.site_settings.models import SiteSetting

from ._utils import app_context_task


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
        'key': 'Setting name, e.g. header_image (note also supports edm configuration keys like site.name)',
    }
)
def get_value(context, key, default=None):
    if not default:
        val = SiteSetting.get_value(key)
    else:
        val = SiteSetting.get_value(key, default=default)
    print(repr(val))
