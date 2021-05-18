# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Keywords resources RESTful API
-----------------------------------------------------------
"""
from flask_restx_patched import Parameters, PatchJSONParameters
from . import schemas


class CreateKeywordParameters(Parameters, schemas.DetailedKeywordSchema):
    class Meta(schemas.DetailedKeywordSchema.Meta):
        pass


class PatchKeywordDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (PatchJSONParameters.OP_REPLACE, PatchJSONParameters.OP_ADD)

    PATH_CHOICES = tuple('/%s' % field for field in ('value',))

    @classmethod
    def add(cls, obj, field, value, state):
        # Add and replace are the same operation so reuse the one method
        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):
        return super(PatchKeywordDetailsParameters, cls).replace(obj, field, value, state)
