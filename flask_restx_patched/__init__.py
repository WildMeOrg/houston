# -*- coding: utf-8 -*-
from flask_restx import *  # NOQA
from .api import Api  # NOQA
from .model import Schema, DefaultHTTPErrorSchema  # NOQA

try:
    from .model import ModelSchema  # NOQA
except ImportError:  # pragma: no cover
    pass

from .namespace import (  # NOQA
    Namespace,  # NOQA
    is_extension_enabled,  # NOQA
    is_module_enabled,  # NOQA
    extension_required,  # NOQA
    module_required,  # NOQA
)  # NOQA
from .parameters import Parameters, PostFormParameters  # NOQA
from .parameters import PatchJSONParameters, PatchJSONParametersWithPassword  # NOQA
from .swagger import Swagger  # NOQA
from .resource import Resource  # NOQA
