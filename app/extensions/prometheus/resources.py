# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Prometheus resources
--------------------------------
"""

import json
import logging
from http import HTTPStatus

from flask import Blueprint, Response, request
from flask_login import current_user
from prometheus_client.metrics import MetricWrapperBase

from app.extensions.api import Namespace, abort
from flask_restx_patched import Resource

log = logging.getLogger(__name__)  # pylint: disable=invalid-name

prometheus = Blueprint('prometheus', __name__)

api = Namespace('prometheus', description='Prometheus')  # pylint: disable=invalid-name


@prometheus.route('/metrics')
def metrics():
    from prometheus_client import generate_latest

    content = generate_latest()
    return Response(content, mimetype='text/plain')


@api.route('/')
@api.login_required(oauth_scopes=['prometheus:read', 'prometheus:write'])
class PrometheusUpdate(Resource):
    @api.response(code=HTTPStatus.FORBIDDEN)
    @api.response(code=HTTPStatus.BAD_REQUEST)
    def post(self):
        from app.extensions import prometheus as current_module

        if not (current_user.is_staff or current_user.is_internal):
            abort(
                HTTPStatus.FORBIDDEN,
                'Not permitted',
            )

        data = request.get_json()
        samples = json.loads(data)

        objs = {}
        for key, value in current_module.__dict__.items():
            if isinstance(value, MetricWrapperBase):
                objs[key] = value

        name_mapping = {
            'houston_info': 'info',
            'info_info': 'info',
            'tasks': 'tasks_',
        }

        for sample in samples:
            try:
                name, labels, value, timestamp, exemplar = sample
                name = name_mapping.get(name, name)
                obj = objs.get(name, None)
                if obj is None:
                    log.warning(
                        'Prometheus background sample unrecognized, skipping: {!r}'.format(
                            sample
                        )
                    )
                else:
                    if name == 'info':
                        obj.info(labels)
                    else:
                        obj.labels(**labels).set(value)
            except Exception:
                log.warning(
                    'Prometheus background sample failed, skipping: {!r}'.format(sample)
                )

        return 'updated'
