# -*- coding: utf-8 -*-
from flask_restx import *  # NOQA

from .api import Api  # NOQA
from .model import DefaultHTTPErrorSchema, Schema  # NOQA

try:
    from .model import ModelSchema  # NOQA
except ImportError:  # pragma: no cover
    pass

from .namespace import Namespace  # NOQA
from .namespace import extension_required  # NOQA
from .namespace import is_extension_enabled  # NOQA
from .namespace import is_module_enabled  # NOQA
from .namespace import module_required  # NOQA; NOQA
from .parameters import PatchJSONParameters  # NOQA
from .parameters import PatchJSONParametersWithPassword  # NOQA
from .parameters import SetOperationsJSONParameters  # NOQA
from .parameters import Parameters, PostFormParameters  # NOQA
from .resource import Resource  # NOQA
from .swagger import Swagger  # NOQA
