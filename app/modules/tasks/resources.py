# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Tasks resources
--------------------------
"""

import logging

from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus
from flask_login import current_user  # NOQA

from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from . import parameters, schemas
from .models import Task


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('tasks', description='Tasks')  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['tasks:read'])
class Tasks(Resource):
    """
    Manipulations with Tasks.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Task,
            'action': AccessOperation.READ,
        },
    )
    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseTaskSchema(many=True))
    def get(self, args):
        """
        List of Task.

        Returns a list of Task starting from ``offset`` limited by ``limit``
        parameter.
        """
        return Task.query.offset(args['offset']).limit(args['limit'])

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Task,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['tasks:write'])
    @api.parameters(parameters.CreateTaskParameters())
    @api.response(schemas.DetailedTaskSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Task.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Task'
        )
        args['owner_guid'] = current_user.guid
        task = Task(**args)
        # User who creates the task gets added to it
        task.add_user(current_user)
        with context:
            db.session.add(task)

        db.session.refresh(task)

        return task


@api.route('/<uuid:task_guid>')
@api.login_required(oauth_scopes=['tasks:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Task not found.',
)
@api.resolve_object_by_model(Task, 'task')
class TaskByID(Resource):
    """
    Manipulations with a specific Task.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['task'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedTaskSchema())
    def get(self, task):
        """
        Get Task details by ID.
        """
        return task

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['task'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['tasks:write'])
    @api.parameters(parameters.PatchTaskDetailsParameters())
    @api.response(schemas.DetailedTaskSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, task):
        """
        Patch Task details by ID.
        """

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Task details.'
        )
        with context:
            parameters.PatchTaskDetailsParameters.perform_patch(args, obj=task)
            db.session.merge(task)
        return task

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['task'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['tasks:delete'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, task):
        """
        Delete a Task by ID.
        """
        task.delete()
        return None
