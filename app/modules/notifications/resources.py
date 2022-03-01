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
from marshmallow import ValidationError
from app.extensions.api import abort

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
class MyNotifications(Resource):
    """
    Manipulations with Users own Notifications.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Notification,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    @api.response(schemas.DetailedNotificationSchema(many=True))
    def get(self, args):
        """
        List of Notifications for the user after preferences applied.

        Returns a list of Notification starting from ``offset`` limited by ``limit``
        parameter.
        """

        returned_notifications = current_user.get_notifications()

        # Manually apply offset and limit after the unique list is created
        return returned_notifications[args['offset'] : args['limit'] - args['offset']]

    # No reason we should allow the frontend to create an arbitrary notification and many security
    # reasons that we should not. Code retained in case this decision is reversed.
    # @api.permission_required(
    #     permissions.ModuleAccessPermission,
    #     kwargs_on_request=lambda kwargs: {
    #         'module': Notification,
    #         'action': AccessOperation.WRITE,
    #     },
    # )
    # @api.login_required(oauth_scopes=['notifications:write'])
    # @api.parameters(parameters.CreateNotificationParameters())
    # @api.response(schemas.DetailedNotificationSchema())
    # @api.response(code=HTTPStatus.CONFLICT)
    # def post(self, args):
    #     """
    #     Create a new instance of Notification.
    #     """
    #     context = api.commit_or_abort(
    #         db.session, default_error_message='Failed to create a new Notification'
    #     )
    #     with context:
    #         notification = Notification(**args)
    #         db.session.add(notification)
    #     return notification


@api.route('/unread')
@api.login_required(oauth_scopes=['notifications:read'])
class MyUnreadNotifications(Resource):
    """
    Manipulations with Users own Unread Notifications.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Notification,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    @api.response(schemas.DetailedNotificationSchema(many=True))
    def get(self, args):
        """
        List of unread Notifications for the user after preferences applied.

        Returns a list of Notification starting from ``offset`` limited by ``limit``
        parameter.
        """
        unread_notifications = current_user.get_unread_notifications()
        # Manually apply offset and limit after the list is created
        return unread_notifications[args['offset'] : args['limit'] - args['offset']]


@api.route('/all_unread')
@api.login_required(oauth_scopes=['notifications:read'])
class AllUnreadNotifications(Resource):
    """
    Manipulations with All Notifications.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Notification,
            'action': AccessOperation.READ_PRIVILEGED,
        },
    )
    @api.parameters(PaginationParameters())
    @api.response(schemas.DetailedNotificationSchema(many=True))
    def get(self, args):
        """
        List of Notifications for all users with no preferences applied.

        Returns a list of Notification starting from ``offset`` limited by ``limit``
        parameter.
        """
        notifications = Notification.query.all()
        # Manually apply offset and limit after the list is created
        return notifications[args['offset'] : args['limit'] - args['offset']]


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
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['notifications:write'])
    @api.parameters(parameters.PatchNotificationDetailsParameters())
    @api.response(schemas.DetailedNotificationSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, notification):
        """
        Patch Notification details by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Notification details.'
        )
        with context:
            try:
                parameters.PatchNotificationDetailsParameters.perform_patch(
                    args, notification
                )
                db.session.merge(notification)
            except ValidationError:
                abort(
                    400, message=f"unable to set {args[0]['path']} to {args[0]['value']}"
                )

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
