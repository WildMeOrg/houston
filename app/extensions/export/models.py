# -*- coding: utf-8 -*-
"""
Export models
--------------------------------------
"""

import logging

from flask_login import current_user

import app.extensions.logging as AuditLog  # NOQA
from app.modules.site_settings.models import SiteSetting

# from app.extensions import HoustonModel, db

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class ExportException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# https://openpyxl.readthedocs.io/en/stable/
class Export:
    """
    Export class
    """

    def __init__(self, *args, **kwargs):
        from openpyxl import Workbook
        from openpyxl.packaging.custom import StringProperty

        self.workbook = Workbook()
        self.workbook.custom_doc_props.append(
            StringProperty(
                name='Codex', value=SiteSetting.get_value('site.name', default='Unknown')
            )
        )
        self.workbook.custom_doc_props.append(
            StringProperty(name='Codex GUID', value=SiteSetting.get_system_guid())
        )
        uname = (
            f'{str(current_user.guid)} {current_user.full_name}'
            if current_user
            else 'Unknown User'
        )
        self.workbook.custom_doc_props.append(
            StringProperty(name='Codex User', value=uname)
        )
        self.worksheet = self.workbook.active
        self.active_class = None
        self.columns = None
        self.filename = self._generate_filename()

    # we only let repeated addition of objects of the same class, as mixing
    #   types *within a sheet* would be bad.  TODO we could create new sheets based on class or something?
    def add(self, obj):
        from app.extensions import ExportMixin

        if not obj or not issubclass(obj.__class__, ExportMixin):
            raise ValueError(f'{obj} is not an ExportMixin')

        if not self.active_class:
            self.active_class = obj.__class__
            self.worksheet.title = f'{obj.__class__.__name__} Results'
            self.set_columns(obj)
        if not isinstance(obj, self.active_class):
            raise ValueError(
                f'{obj} does not match current worksheet class {self.active_class}'
            )
        self.worksheet.append(self.row(obj))

    def set_columns(self, obj):
        exd = obj.export_data
        self.columns = list(exd.keys())
        self.columns.sort()
        # for now we set first row to be headers by default
        self.worksheet.append(self.columns)

    def row(self, obj):
        exd = obj.export_data
        row = []
        for col in self.columns:
            row.append(exd.get(col))
        return row

    # since this is based on timestamp, we set at init but should not use this directly (later)
    def _generate_filename(self):
        import re
        from datetime import datetime

        from app.utils import to_ascii

        site_name = to_ascii(SiteSetting.get_value('site.name', default='Unknown'))
        site_name = re.sub(r'\W+', '-', site_name)
        dt = datetime.now().strftime('%Y%m%d%H%M')
        return f'codex-export-{site_name}-{dt}.xls'

    @property
    def filepath(self):
        import os

        udir = str(current_user.guid) if current_user else 'unknown_user'
        target_dir = os.path.join('/tmp', 'export', udir)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        return os.path.join(target_dir, self.filename)

    def save(self):
        log.info(f'{self} saving to {self.filepath}')
        self.workbook.save(self.filepath)
        return self.filename
