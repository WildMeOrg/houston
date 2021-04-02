# -*- coding: utf-8 -*-
from pathlib import Path

from app.modules.fileuploads.models import FileUpload
from app.modules.site_settings.models import SiteSetting


def test_create_header_image(db, flask_app):
    project_root = Path(flask_app.config['PROJECT_ROOT'])
    fup = FileUpload.create_fileupload_from_path(
        str(project_root / 'tests/submissions/test-000/zebra.jpg'), copy=True
    )
    fup2 = FileUpload.create_fileupload_from_path(
        str(project_root / 'tests/submissions/test-000/fluke.jpg'), copy=True
    )
    with db.session.begin():
        db.session.add(fup)
        db.session.add(fup2)
    header_image = SiteSetting.set(key='header_image', file_upload_guid=fup.guid)
    try:
        assert (
            repr(header_image)
            == f"<SiteSetting(key='header_image' file_upload_guid='{fup.guid}' public=True)>"
        )
        # Set header image again
        SiteSetting.set(key='header_image', file_upload_guid=fup2.guid)
        assert SiteSetting.query.count() == 1
    finally:
        db.session.delete(header_image)
        fup.delete()
        # The fileupload object should be deleted already
        assert FileUpload.query.filter(FileUpload.guid == fup2.guid).first() is None
        file_path = Path(fup2.get_absolute_path())
        if file_path.exists():
            file_path.unlink()
