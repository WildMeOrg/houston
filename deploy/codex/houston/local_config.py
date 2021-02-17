# -*- coding: utf-8 -*-
import os
from pathlib import Path

from config import ProductionConfig as BaseConfig


DATA_ROOT = Path(os.getenv('DATA_ROOT', '/data/var'))


class LocalConfig(BaseConfig):
    DEBUG = True

    PROJECT_DATABASE_PATH = str(DATA_ROOT)
    SUBMISSIONS_DATABASE_PATH = str(DATA_ROOT / 'submissions')
    ASSET_DATABASE_PATH = str(DATA_ROOT / 'assets')
    SQLALCHEMY_DATABASE_PATH = str(DATA_ROOT / 'database.sqlite3')

    SECRET_KEY = 'seekret'
    SENTRY_DSN = None

    EDM_URIS = {
        0: os.getenv('EDM_AUTHENTICATIONS_0_URI'),
    }
    EDM_AUTHENTICATIONS = {
        0: {
            'username' : os.getenv('EDM_AUTHENTICATIONS_0_USERNAME'),
            'password' : os.getenv('EDM_AUTHENTICATIONS_0_PASSWORD'),
        },
    }
