# -*- coding: utf-8 -*-
from config import ProductionConfig as BaseConfig


class LocalConfig(BaseConfig):
    DEBUG = True
    SECRET_KEY = 'seekret'
    SENTRY_DSN = None
