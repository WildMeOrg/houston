# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Config resources RESTful API
-----------------------------------------------------------
"""

from app.extensions import _CONFIG_PATH_CHOICES
from app.houston import PatchJSONParametersWithPassword
from .models import HoustonConfig


# noinspection PyAbstractClass
class PatchHoustonConfigParameters(PatchJSONParametersWithPassword):
    VALID_FIELDS = _CONFIG_PATH_CHOICES + ['current_password']
    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

    @classmethod
    def set_field(cls, obj, field, value, state):
        HoustonConfig.set(field, value)
        return True

    @classmethod
    def forget_field(cls, obj, field, state):
        HoustonConfig.forget(field)
        return True

    @classmethod
    def replace(cls, obj, field, value, state):
        raise NotImplementedError()
