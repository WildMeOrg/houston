# -*- coding: utf-8 -*-
# pylint: disable=bad-continuation
"""
RESTful API Missions resources
--------------------------
"""

import logging
import werkzeug
import uuid

from flask import request
from flask_restx_patched import Resource
from flask_restx_patched._http import HTTPStatus
from flask_login import current_user  # NOQA

from app.extensions import db
from app.extensions.api import Namespace, abort
from app.modules.users import permissions
from app.modules.users.permissions.types import AccessOperation
from app.modules.assets.schemas import DetailedAssetTableSchema
from . import parameters, schemas
from .models import Mission, MissionCollection, MissionTask
from marshmallow import ValidationError
import randomname
import tqdm

from app.utils import HoustonException


USE_GLOBALLY_UNIQUE_MISSION_TASK_NAMES = True


log = logging.getLogger(__name__)  # pylint: disable=invalid-name
api = Namespace('missions', description='Missions')  # pylint: disable=invalid-name


# the resolve_object_by_model returns a tuple if the return_not_found is set as it is here
# a common helper to get the mission_collection object or raise 428 if remote only
def _get_mission_collection_with_428(mission_collection):
    mission_collection, mission_collection_guids = mission_collection
    if mission_collection is not None:
        return mission_collection

    # We did not find the mission_collection by its UUID in the Houston database
    # We now need to check the GitlabManager for the existence of that repo
    mission_collection_guid = mission_collection_guids[0]
    assert isinstance(mission_collection_guid, uuid.UUID)

    if MissionCollection.is_on_remote(mission_collection_guid):
        # Mission Collection is not local but is on remote
        log.info(f'Mission Collection {mission_collection_guid} on remote but not local')
        raise werkzeug.exceptions.PreconditionRequired
    else:
        # Mission Collection neither local nor remote
        return None


@api.route('/')
@api.login_required(oauth_scopes=['missions:read'])
class Missions(Resource):
    """
    Manipulations with Missions.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Mission,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseMissionSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Mission.
        """
        return Mission.query_search(args=args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Mission,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['missions:write'])
    @api.parameters(parameters.CreateMissionParameters())
    @api.response(schemas.DetailedMissionSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args):
        """
        Create a new instance of Mission.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new Mission'
        )
        args['owner'] = current_user
        mission = Mission(**args)
        # User who creates the mission gets added to it
        mission.add_user(current_user)
        with context:
            db.session.add(mission)

        db.session.refresh(mission)

        return mission


@api.route('/search')
@api.login_required(oauth_scopes=['missions:read'])
class MissionElasticsearch(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Mission,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseMissionSchema(many=True))
    @api.paginate()
    def get(self, args):
        search = {}
        args['total'] = True
        return Mission.elasticsearch(search, **args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Mission,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseMissionSchema(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()

        args['total'] = True
        return Mission.elasticsearch(search, **args)


@api.route('/<uuid:mission_guid>')
@api.login_required(oauth_scopes=['missions:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Mission not found.',
)
@api.resolve_object_by_model(Mission, 'mission')
class MissionByID(Resource):
    """
    Manipulations with a specific Mission.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedMissionSchema())
    def get(self, mission):
        """
        Get Mission details by ID.
        """
        return mission

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['missions:write'])
    @api.parameters(parameters.PatchMissionDetailsParameters())
    @api.response(schemas.DetailedMissionSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, mission):
        """
        Patch Mission details by ID.
        """

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update Mission details.'
        )
        with context:
            parameters.PatchMissionDetailsParameters.perform_patch(args, mission)
            db.session.merge(mission)
        return mission

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['missions:delete'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, mission):
        """
        Delete a Mission by ID.
        """
        mission.delete_cascade()
        return None


@api.route('/<uuid:mission_guid>/tus/collect')
@api.login_required(oauth_scopes=['missions:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Mission not found.',
)
@api.resolve_object_by_model(Mission, 'mission')
class MissionTusCollect(Resource):
    """
    Collect files uploaded by Tus endpoint for this Mission Collection
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['missions:write'])
    @api.parameters(parameters.CreateMissionCollectionParameters())
    @api.response(schemas.DetailedMissionCollectionSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args, mission):
        """
        Alias of [POST] /api/v1/missions/<uuid:mission_guid>/collections/
        """
        args['owner'] = current_user
        args['mission'] = mission
        mission_collection = MissionCollection.create_from_tus(**args)
        db.session.refresh(mission_collection)
        return mission_collection


@api.route('/<uuid:mission_guid>/collections')
@api.login_required(oauth_scopes=['missions:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Mission not found.',
)
@api.resolve_object_by_model(Mission, 'mission')
class MissionCollectionsForMission(Resource):
    """
    List a Mission's Mission Collections.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.response(schemas.DetailedMissionCollectionSchema(many=True))
    def get(self, mission):
        return mission.collections

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['missions:write'])
    @api.parameters(parameters.CreateMissionCollectionParameters())
    @api.response(schemas.DetailedMissionCollectionSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args, mission):

        args['owner'] = current_user
        args['mission'] = mission
        mission_collection = MissionCollection.create_from_tus(**args)
        return mission_collection


@api.route('/<uuid:mission_guid>/assets')
@api.login_required(oauth_scopes=['missions:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Mission not found.',
)
@api.resolve_object_by_model(Mission, 'mission')
class AssetsForMission(Resource):
    """
    Manipulations with Mission Tasks.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(DetailedAssetTableSchema(many=True))
    @api.paginate()
    def get(self, args, mission):
        search = {}
        return mission.asset_search(search, **args)

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(DetailedAssetTableSchema(many=True))
    @api.paginate()
    def post(self, args, mission):
        search = request.get_json()
        return mission.asset_search(search, **args)


@api.route('/<uuid:mission_guid>/tasks')
@api.login_required(oauth_scopes=['missions:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Mission not found.',
)
@api.resolve_object_by_model(Mission, 'mission')
class MissionTasksForMission(Resource):
    """
    Manipulations with Mission Tasks.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.response(schemas.DetailedMissionCollectionSchema(many=True))
    def get(self, mission):
        return mission.tasks

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': Mission,
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['missions:write'])
    @api.parameters(parameters.CreateMissionTaskParameters())
    @api.response(schemas.DetailedMissionTaskSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args, mission):
        """
        Create a new instance of Mission.
        """
        from app.modules.assets.models import Asset

        try:
            asset_set = parameters.CreateMissionTaskParameters.perform_set_operations(
                args, obj=mission, obj_cls=Asset
            )
        except ValidationError as exception:
            abort(409, message=str(exception))

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new MissionTask'
        )

        # Pick a random title with an adjective nown structure (see here: https://github.com/imsky/wordlists)
        if USE_GLOBALLY_UNIQUE_MISSION_TASK_NAMES:
            current_tasks = MissionTask.query.all()
        else:
            current_tasks = mission.tasks
        titles = [task.title for task in current_tasks]
        title = None
        while title in titles + [None]:
            title = randomname.get_name(
                adj=(
                    'character',
                    'colors',
                    'emotions',
                    'shape',
                ),
                noun=(
                    'apex_predators',
                    'birds',
                    'cats',
                    'dogs',
                    'fish',
                ),
                sep=' ',
            ).title()
            title = 'New Task: %s' % (title,)
        assert title is not None
        assert title not in titles

        args = {}
        args['title'] = title
        args['owner'] = current_user
        args['mission'] = mission
        mission_task = MissionTask(**args)

        with context:
            db.session.add(mission_task)
            mission_task.add_user_in_context(current_user)
            for asset in tqdm.tqdm(asset_set, desc='Adding Assets to MissionTask'):
                mission_task.add_asset_in_context(asset)

        db.session.refresh(mission_task)

        return mission_task


@api.route('/collections')
@api.login_required(oauth_scopes=['missions:read'])
class MissionCollections(Resource):
    """
    Manipulations with Mission Collections.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': MissionCollection,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseMissionCollectionSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Mission Collection.
        """
        return MissionCollection.query_search(args=args)


@api.route('/collections/search')
@api.login_required(oauth_scopes=['missions:read'])
class MissionCollectionElasticsearch(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': MissionCollection,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseMissionCollectionSchema(many=True))
    @api.paginate()
    def get(self, args):
        search = {}
        args['total'] = True
        return MissionCollection.elasticsearch(search, **args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': MissionCollection,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseMissionCollectionSchema(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()

        args['total'] = True
        return MissionCollection.elasticsearch(search, **args)


@api.login_required(oauth_scopes=['missions:read'])
@api.route('/collections/<uuid:mission_collection_guid>')
@api.resolve_object_by_model(
    MissionCollection, 'mission_collection', return_not_found=True
)
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='Mission Collection not found.',
)
@api.response(
    code=HTTPStatus.PRECONDITION_REQUIRED,
    description='Mission Collection not local, need to post',
)
class MissionCollectionByID(Resource):
    """
    Manipulations with a specific Mission Collection.
    """

    @api.permission_required(
        permissions.ModuleOrObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': MissionCollection,
            'obj': kwargs['mission_collection'][0],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedMissionCollectionSchema())
    def get(self, mission_collection):
        """
        Get Mission Collection details by ID.

        If mission_collection is not found locally in database, but is on the remote Github,
        a 428 PRECONDITION_REQUIRED will be returned.

        If mission_collection is not local and not on remote github, 404 will be returned.

        Otherwise the mission_collection will be returned
        """
        mission_collection = _get_mission_collection_with_428(mission_collection)
        if mission_collection is None:
            raise werkzeug.exceptions.NotFound

        return mission_collection

    @api.login_required(oauth_scopes=['missions:write'])
    @api.permission_required(
        permissions.ModuleOrObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': MissionCollection,
            'obj': kwargs['mission_collection'][0],
            'action': AccessOperation.WRITE,
        },
    )
    @api.response(schemas.DetailedMissionCollectionSchema())
    def post(self, mission_collection):
        """
        Post Mission Collection details by ID. (Actually a get with clone)

        If mission_collection is not found locally in database, but is on the remote Github,
        it will be cloned from the remote github

        If mission_collection is not local and not on remote github, 404 will be returned.

        Otherwise the mission_collection will be returned
        """
        mission_collection, mission_collection_guids = mission_collection
        if mission_collection is not None:
            log.info(
                f'Mission Collection {mission_collection.guid} found locally on post'
            )
            return mission_collection

        # We did not find the mission_collection by its UUID in the Houston database
        # We now need to check the GitlabManager for the existence of that repo
        mission_collection_guid = mission_collection_guids[0]
        assert isinstance(mission_collection_guid, uuid.UUID)

        # Clone if present on gitlab
        mission_collection = MissionCollection.ensure_store(mission_collection_guid)
        if mission_collection is None:
            # We have checked the mission_collection manager and cannot find this mission_collection, raise 404 manually
            raise werkzeug.exceptions.NotFound

        return mission_collection

    @api.permission_required(
        permissions.ModuleOrObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': MissionCollection,
            'obj': kwargs['mission_collection'][0],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['missions:write'])
    @api.parameters(parameters.PatchMissionCollectionDetailsParameters())
    @api.response(schemas.DetailedMissionCollectionSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, mission_collection):
        """
        Patch Mission Collection details by ID.

        If mission_collection is not found locally in database, but is on the remote Github,
        a 428 PRECONDITION_REQUIRED will be returned.

        If mission_collection is not local and not on remote github, 404 will be returned.

        Otherwise the mission_collection will be patched
        """
        mission_collection = _get_mission_collection_with_428(mission_collection)
        if mission_collection is None:
            raise werkzeug.exceptions.NotFound

        context = api.commit_or_abort(
            db.session,
            default_error_message='Failed to update Mission Collection details.',
        )
        with context:
            parameters.PatchMissionCollectionDetailsParameters.perform_patch(
                args, mission_collection
            )
            db.session.merge(mission_collection)
        return mission_collection

    @api.permission_required(
        permissions.ModuleOrObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': MissionCollection,
            'obj': kwargs['mission_collection'][0],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['missions:write'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, mission_collection):
        """
        Delete an Mission Collection by ID.
        """
        _, mission_collection_id = mission_collection
        mission_collection = _get_mission_collection_with_428(mission_collection)

        if mission_collection is not None:
            try:
                mission_collection.delete()
            except HoustonException as ex:
                abort(ex.status_code, ex.message)
        else:
            from app.extensions.git_store.tasks import delete_remote

            delete_remote.delay(str(mission_collection_id))

        return None


@api.route('/tasks')
@api.login_required(oauth_scopes=['missions:read'])
class MissionTasks(Resource):
    """
    Manipulations with Mission Tasks.
    """

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': MissionTask,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseMissionTaskSchema(many=True))
    @api.paginate()
    def get(self, args):
        """
        List of Mission Task.
        """
        return MissionTask.query_search(args=args)


@api.route('/tasks/search')
@api.login_required(oauth_scopes=['missions:read'])
class MissionTaskElasticsearch(Resource):
    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': MissionTask,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseMissionTaskSchema(many=True))
    @api.paginate()
    def get(self, args):
        search = {}
        args['total'] = True
        return MissionTask.elasticsearch(search, **args)

    @api.permission_required(
        permissions.ModuleAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'module': MissionTask,
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.BaseMissionTaskSchema(many=True))
    @api.paginate()
    def post(self, args):
        search = request.get_json()
        args['total'] = True

        return MissionTask.elasticsearch(search, **args)


@api.route('/tasks/<uuid:mission_task_guid>')
@api.login_required(oauth_scopes=['missions:read'])
@api.response(
    code=HTTPStatus.NOT_FOUND,
    description='MissionTask not found.',
)
@api.resolve_object_by_model(MissionTask, 'mission_task')
class MissionTaskByID(Resource):
    """
    Manipulations with a specific MissionTask.
    """

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission_task'],
            'action': AccessOperation.READ,
        },
    )
    @api.response(schemas.DetailedMissionTaskSchema())
    def get(self, mission_task):
        """
        Get MissionTask details by ID.
        """
        return mission_task

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission_task'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['missions:write'])
    @api.parameters(parameters.CreateMissionTaskParameters())
    @api.response(schemas.DetailedMissionTaskSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def post(self, args, mission_task):
        """
        Create a new instance of Mission.
        """
        from app.modules.assets.models import Asset

        starting_set = set(mission_task.assets)
        try:
            asset_set = parameters.CreateMissionTaskParameters.perform_set_operations(
                args, obj=mission_task.mission, obj_cls=Asset, starting_set=starting_set
            )
        except ValidationError as exception:
            abort(409, message=str(exception))

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to create a new MissionTask'
        )

        with context:
            add_set = asset_set - starting_set
            for asset in add_set:
                mission_task.add_asset_in_context(asset)

            remove_set = starting_set - asset_set
            for asset in remove_set:
                mission_task.remove_asset_in_context(asset)

            db.session.merge(mission_task)

        db.session.refresh(mission_task)

        return mission_task

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission_task'],
            'action': AccessOperation.WRITE,
        },
    )
    @api.login_required(oauth_scopes=['missions:write'])
    @api.parameters(parameters.PatchMissionTaskDetailsParameters())
    @api.response(schemas.DetailedMissionTaskSchema())
    @api.response(code=HTTPStatus.CONFLICT)
    def patch(self, args, mission_task):
        """
        Patch MissionTask details by ID.
        """

        context = api.commit_or_abort(
            db.session, default_error_message='Failed to update MissionTask details.'
        )
        with context:
            parameters.PatchMissionTaskDetailsParameters.perform_patch(args, mission_task)
            db.session.merge(mission_task)
        return mission_task

    @api.permission_required(
        permissions.ObjectAccessPermission,
        kwargs_on_request=lambda kwargs: {
            'obj': kwargs['mission_task'],
            'action': AccessOperation.DELETE,
        },
    )
    @api.login_required(oauth_scopes=['missions:delete'])
    @api.response(code=HTTPStatus.CONFLICT)
    @api.response(code=HTTPStatus.NO_CONTENT)
    def delete(self, mission_task):
        """
        Delete a MissionTask by ID.
        """
        context = api.commit_or_abort(
            db.session, default_error_message='Failed to delete MissionTask'
        )
        with context:
            mission_task.delete_cascade()
        return None
