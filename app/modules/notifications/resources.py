# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Notifications resources
--------------------------
"""

import logging

from flask_login import current_user  # NOQA
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus

from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation


from . import parameters, schemas
from .models import Notification


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace(
    'notifications', description='Notifications'
)  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['notifications:read'])
class Notifications(Resource):
    """
    Manipulations with Notifications.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Notification,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseNotificationSchema(many=True))
    def get(self, args):
        """
        List of Notification.

        Returns a list of Notification starting from ``offset`` limited by ``limit``
        parameter.
        """
        all_notifications = Notification.query.offset(args['offset']).limit(args['limit'])
        if current_user.is_user_manager:
            returned_notifications = all_notifications
        else:
            returned_notifications = [
                notif for notif in all_notifications if notif.recipient == current_user
            ]
        return returned_notifications

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Notification,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['notifications:write'])
    @api.parameters(parameters.CreateNotificationParameters())
    @api.response(schemas.DetailedNotificationSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Notification.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Notification'
        )
        with context:
            notification = Notification(**args)
            db.session.add(notification)
        return notification


@api.route('/<uuid:notification_guid>')
@api.login_required(oauth_scopes=['notifications:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Notification not found.',
)
@api.resolve_object_by_model(Notification, 'notification')
class NotificationByID(Resource):
    """
    Manipulations with a specific Notification.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['notification'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedNotificationSchema())
    def get(self, notification):
        """
        Get Notification details by ID.
        """
        return notification

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['notification'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['notifications:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, notification):
        """
        Delete a Notification by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to delete the Notification.'
        )
        with context:
            db.session.delete(notification)
        return None
