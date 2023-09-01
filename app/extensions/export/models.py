# -*- coding: utf-8 -*-
"""
Export models
--------------------------------------
"""

import logging

import app.extensions.logging as AuditLog  # NOQA

# from flask import current_app, url_for

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

        self.workbook = Workbook()
        self.worksheet = self.workbook.active

    # ws.append([1, 2, 3])

    @property
    def filename(self):
        return f'tmp123{self}'

    @property
    def path(self):
        return f'/tmp/{self.filename}'

    def save(self):
        log.info(f'{self} saving to {self.path}')
        self.workbook.save(self.path)
        return self.filename
