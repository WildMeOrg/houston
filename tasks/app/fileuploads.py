# -*- coding: utf-8 -*-
"""
Application FileUpload management related tasks for Invoke.
"""

from ._utils import app_context_task


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

    fup = FileUpload.create_fileupload_from_path(filepath, None, copy=True)
    print(fup)
