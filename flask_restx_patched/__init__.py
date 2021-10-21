# -*- coding: utf-8 -*-
from flask_restx import *  # NOQA
from .api import Api  # NOQA
from .model import Schema, DefaultHTTPErrorSchema  # NOQA

try:
    from .model import ModelSchema  # NOQA
except ImportError:  # pragma: no cover
    pass

from .namespace import Namespace  # NOQA
from .namespace import is_extension_enabled, is_module_enabled, extension_required, module_required  # NOQA
from .parameters import Parameters, PostFormParameters  # NOQA
from .parameters import PatchJSONParameters, PatchJSONParametersWithPassword  # NOQA
from .swagger import Swagger  # NOQA
from .resource import Resource  # NOQA
