# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Config resources RESTful API
-----------------------------------------------------------
"""
from flask_restplus_patched import PatchJSONParametersWithPassword
from app.extensions import _CONFIG_PATH_CHOICES
from .models import HoustonConfig


# noinspection PyAbstractClass
class PatchHoustonConfigParameters(PatchJSONParametersWithPassword):
    VALID_FIELDS = _CONFIG_PATH_CHOICES + ['current_password']
    PATH_CHOICES = tuple('/%s' % field for field in VALID_FIELDS)

    @classmethod
    def add(cls, obj, field, value, state):
        super(PatchHoustonConfigParameters, cls).add(obj, field, value, state)
        HoustonConfig.set(field, value)
        return True

    @classmethod
    def remove(cls, obj, field, value, state):
        super(PatchHoustonConfigParameters, cls).remove(obj, field, value, state)

        HoustonConfig.forget(field)
        return True

    @classmethod
    def replace(cls, obj, field, value, state):
        raise NotImplementedError()
