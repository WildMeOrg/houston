# -*- coding: utf-8 -*-
import os
from pathlib import Path

from config import ProductionConfig as BaseConfig


DATA_ROOT = Path(os.getenv('DATA_ROOT', '/data/var'))


class LocalConfig(BaseConfig):
    DEBUG = True
    REVERSE_PROXY_SETUP = True

    PROJECT_DATABASE_PATH = str(DATA_ROOT)
    SUBMISSIONS_DATABASE_PATH = str(DATA_ROOT / 'submissions')
    ASSET_DATABASE_PATH = str(DATA_ROOT / 'assets')
    UPLOADS_DATABASE_PATH = str(DATA_ROOT / 'uploads')
    SQLALCHEMY_DATABASE_PATH = str(DATA_ROOT / 'database.sqlite3')

    SECRET_KEY = 'seekret'
    SENTRY_DSN = None

    # FIXME: There is code that won't allow for `SQLALCHEMY_DATABASE_PATH = None`
    #        File "/code/tasks/app/db.py", in upgrade: `if os.path.exists(_db_filepath):`
    # SQLALCHEMY_DATABASE_PATH = None
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
