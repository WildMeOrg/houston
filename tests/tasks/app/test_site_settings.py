# -*- coding: utf-8 -*-
import io
from pathlib import Path
from unittest import mock

from invoke import MockContext

from app.modules.site_settings.models import SiteSetting


def test_site_settings(flask_app, db, request, test_root):
    def cleanup():
        header_image = SiteSetting.query.get('logo')
        if header_image:
            file_path = Path(header_image.file_upload.get_absolute_path())
            with db.session.begin():
                db.session.delete(header_image)
            if file_path.exists():
                file_path.unlink()

    request.addfinalizer(cleanup)
    test_image = test_root / 'zebra.jpg'

    with mock.patch('app.create_app'):
        with mock.patch('sys.stdout', new=io.StringIO()) as stdout:
            from tasks.app import site_settings

            site_settings.set(MockContext(), 'logo', str(test_image))
            set_output = stdout.getvalue().strip()
            last_line = set_output.split('\n')[-1].strip()

            assert last_line.startswith(
                "<SiteSetting(key='logo' file_upload_guid='"
            ), last_line

        with mock.patch('sys.stdout', new=io.StringIO()) as stdout:
            site_settings.get(MockContext(), 'logo')
            new_line = stdout.getvalue().strip()
            assert new_line == last_line
