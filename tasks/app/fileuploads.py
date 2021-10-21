# -*- coding: utf-8 -*-
"""
Application FileUpload management related tasks for Invoke.
"""

from tasks.utils import app_context_task


@app_context_task(
    help={
        'filepath': '/path/to/local/file.foo',
    }
)
def from_file(context, filepath):
    """
    Create a FileUpload from a local filepath
    """
    from app.modules.fileuploads.models import FileUpload

    fup = FileUpload.create_fileupload_from_path(filepath, copy=True)

    from app.extensions import db

    with db.session.begin():
        db.session.add(fup)
    print(fup)


@app_context_task(
    help={
        'guid': 'FileUpload guid',
    }
)
def delete(context, guid):
    """
    Delete a FileUpload (and file)
    """
    from app.modules.fileuploads.models import FileUpload

    fup = FileUpload.query.get(guid)
    if fup is None:
        raise Exception('FileUpload with this guid does not exist.')
    fup.delete()
