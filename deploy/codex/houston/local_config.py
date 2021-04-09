# -*- coding: utf-8 -*-
from config import ProductionConfig as BaseConfig


class LocalConfig(BaseConfig):
    DEBUG = True
    REVERSE_PROXY_SETUP = True

    SECRET_KEY = 'seekret'
