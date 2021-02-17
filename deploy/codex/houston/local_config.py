# -*- coding: utf-8 -*-
import os

from config import ProductionConfig as BaseConfig


class LocalConfig(BaseConfig):
    DEBUG = True
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
