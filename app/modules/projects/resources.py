# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Projects resources
--------------------------
"""

import logging

# from flask_login import current_user
from flask_restplus_patched import Resource
from flask_restplus._http import HTTPStatus

from app.extensions import db
from app.extensions.api import Namespace
from app.extensions.api.parameters import PaginationParameters
from app.modules.users import permissions


from . import parameters, schemas
from .models import Project


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('projects', description='Projects')  # pylint: disable=invalid-name


@api.route('/')
@api.login_required(oauth_scopes=['projects:read'])
class Projects(Resource):
    """
    Manipulations with Projects.
    """

    @api.parameters(PaginationParameters())
    @api.response(schemas.BaseProjectSchema(many=True))
    def get(self, args):
        """
        List of Project.

        Returns a list of Project starting from ``offset`` limited by ``limit``
        parameter.
        """
        return Project.query.offset(args['offset']).limit(args['limit'])

    @api.login_required(oauth_scopes=['projects:write'])
    @api.parameters(parameters.CreateProjectParameters())
    @api.response(schemas.DetailedProjectSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Project.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Project'
        )
        with context:
            project = Project(**args)
            db.session.add(project)
        return project


@api.route('/<uuid:project_guid>')
@api.login_required(oauth_scopes=['projects:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Project not found.',
)
@api.resolve_object_by_model(Project, 'project')
class ProjectByID(Resource):
    """
    Manipulations with a specific Project.
    """

    @api.response(schemas.DetailedProjectSchema())
    def get(self, project):
        """
        Get Project details by ID.
        """
        return project

    @api.login_required(oauth_scopes=['projects:write'])
    @api.permission_required(permissions.WriteAccessPermission())
    @api.parameters(parameters.PatchProjectDetailsParameters())
    @api.response(schemas.DetailedProjectSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, project):
        """
        Patch Project details by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Project details.'
        )
        with context:
            parameters.PatchProjectDetailsParameters.perform_patch(args, obj=project)
            db.session.merge(project)
        return project

    @api.login_required(oauth_scopes=['projects:write'])
    @api.permission_required(permissions.WriteAccessPermission())
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, project):
        """
        Delete a Project by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to delete the Project.'
        )
        with context:
            db.session.delete(project)
        return None
