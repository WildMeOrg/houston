# -*- coding: utf-8 -*-
from importlib import import_module
import os
import pathlib
import tempfile
import uuid
from unittest import mock

import sqlalchemy
import pytest
from flask_login import current_user, login_user, logout_user
from flask_restx_patched import is_module_enabled

from app import create_app
from config import CONTEXT_ENVIRONMENT_VARIABLE, VALID_CONTEXTS

from . import (
    utils,
    TEST_ASSET_GROUP_UUID,
    TEST_EMPTY_ASSET_GROUP_UUID,
    TEST_MISSION_COLLECTION_UUID,
    TEST_EMPTY_MISSION_COLLECTION_UUID,
)


# Force FLASK_ENV to be testing instead of using what's defined in the environment
os.environ['FLASK_ENV'] = 'testing'


# Import all models first for db.relationship to avoid model look up
# error:
#
# sqlalchemy.exc.InvalidRequestError: When initializing mapper
# mapped class AssetGroupSighting->asset_group_sighting, expression
# 'Sighting' failed to locate a name ('Sighting'). If this is a
# class name, consider adding this relationship() to the <class
# 'app.modules.asset_groups.models.AssetGroupSighting'> class after
# both dependent classes have been defined.
project_root = pathlib.Path(__file__).parent.parent
for models in project_root.glob('app/modules/*/models.py'):
    models_path = models.relative_to(project_root)
    models_module = str(models_path).replace('.py', '').replace('/', '.')
    module_name = models_module.strip().split('.')[-2]
    if is_module_enabled(module_name):
        import_module(models_module)


def pytest_addoption(parser):
    parser.addoption(
        '--gitlab-remote-login-pat',
        action='append',
        default=[],
        help=('Specify additional config argument for GitLab'),
    )


def _skip_on_app_context(config, items):
    """Use the ``pytest.mark.only_for_{app_context}`` decorator
    to skip a test that is not within the current application context.
    For example, if you are writing a test that is only for MWS,
    use `pytest.mark.only_for_mws`.

    """
    # Which variant of the app are we running under?
    app_context = os.getenv(CONTEXT_ENVIRONMENT_VARIABLE)

    # Create a skip marker for apps outside the current app context
    skip_reason = f"only running tests for the '{app_context}' app context"
    skip = pytest.mark.skip(reason=skip_reason)

    # Define the `pytest.mark.only_for_{app_context}` markers to skip
    keywords_to_skip = []
    for context in VALID_CONTEXTS:
        if context != app_context:
            keywords_to_skip.append(f'only_for_{context}')

    # Roll over the test items, skipping as needed
    for item in items:
        for kw in keywords_to_skip:
            if kw in item.keywords:
                item.add_marker(skip)


def _keyword_skip(config, items):
    """Skips based on keywords used in the marker.

    Available skips:

    - Use the ``pytest.mark.requires_local_gitlab`` decorator
      to skip a test if a gitlab is not locally installed.
      This also skips if gitlab is unavailable.

    """
    # Are we using a local gitlab?
    gitlab_host = os.getenv('GITLAB_HOST')
    gitlab_uri = os.getenv('GITLAB_REMOTE_URI')
    is_local_gitlab = (
        #: to account for when locally run in docker as 'gitlab'
        gitlab_host == 'gitlab'
        #: to account for when gitlab backend connection is disabled
        and not gitlab_uri != '-'
    )

    # Create a keyword lists and skip objects
    keyword_skips = [
        # (skipping condition, keywords, skip object)
        (
            not is_local_gitlab,  # only skip if not local
            ['requires_local_gitlab'],
            pytest.mark.skip(reason='test requires a local instance of gitlab'),
        ),
    ]

    # Iterate over the defined keyword skip pairs
    for should_skip, keywords_to_skip, skip in keyword_skips:
        if not should_skip:
            # According to the condition we shouldn't modify any tests
            continue
        # Roll over the test items, skipping as needed
        for item in items:
            for kw in keywords_to_skip:
                if kw in item.keywords:
                    item.add_marker(skip)


def pytest_collection_modifyitems(config, items):
    """Modify the collected tests... See also
    https://doc.pytest.org/en/latest/how-to/writing_hook_functions.html#hook-function-validation-and-execution

    """
    _skip_on_app_context(config, items)
    _keyword_skip(config, items)


def pytest_generate_tests(metafunc):
    if 'gitlab_remote_login_pat' in metafunc.fixturenames:
        values = list(set(metafunc.config.option.gitlab_remote_login_pat))
        if len(values) == 0:
            value = [None]
        elif len(values) == 1:
            value = values
        else:
            raise ValueError
        metafunc.parametrize('gitlab_remote_login_pat', value, scope='session')


@pytest.fixture(autouse=True)
def check_cleanup_objects(db):
    count = utils.all_count(db)
    yield
    assert count == utils.all_count(
        db
    ), 'Some objects created in the test need to be cleaned up'


@pytest.fixture(autouse=True)
def cleanup_objects(db):
    # This deletes all notifications in the system, the reason being that when many
    # notifications are used, they are marked as read and cannot be recreated. This is intentional by design
    # But it means that the tests can be non deterministic in that they can work or fail depending on what has
    # happened before. The tests may create notifications themselves but they may also be created by the system
    # and the test cannot delete them, so it is done here
    from app.modules.notifications.models import Notification

    notifs = Notification.query.all()
    for notif in notifs:
        with db.session.begin(subtransactions=True):
            db.session.delete(notif)


@pytest.fixture(scope='session')
def flask_app(gitlab_remote_login_pat):
    with tempfile.TemporaryDirectory() as td:
        config_override = {}
        if gitlab_remote_login_pat is not None:
            config_override['GITLAB_REMOTE_LOGIN_PAT'] = gitlab_remote_login_pat
        # Override all the directory settings
        config_override['PROJECT_DATABASE_PATH'] = td
        config_override['ASSET_GROUP_DATABASE_PATH'] = str(
            pathlib.Path(td) / 'asset_group'
        )
        config_override['MISSION_COLLECTION_DATABASE_PATH'] = str(
            pathlib.Path(td) / 'mission_collection'
        )
        config_override['ASSET_DATABASE_PATH'] = str(pathlib.Path(td) / 'assets')
        config_override['UPLOADS_DATABASE_PATH'] = str(pathlib.Path(td) / 'uploads')
        config_override['FILEUPLOAD_BASE_PATH'] = str(pathlib.Path(td) / 'fileuploads')
        config_override['SQLALCHEMY_DATABASE_PATH'] = str(
            pathlib.Path(td) / 'database.sqlite3'
        )

        app = create_app(config_override=config_override)
        from app.extensions import db

        with app.app_context() as ctx:
            try:
                db.create_all()
            except sqlalchemy.exc.OperationalError as e:
                if 'does not exist' in str(e):
                    db_uri, dbname = app.config['SQLALCHEMY_DATABASE_URI'].rsplit('/', 1)
                    engine = sqlalchemy.create_engine(db_uri)
                    engine.execution_options(isolation_level='AUTOCOMMIT').execute(
                        f'CREATE DATABASE {dbname}'
                    )
                    engine.dispose()
                    db.create_all()
                else:
                    raise

            if utils.redis_unavailable():
                # Run code in foreground if redis not available
                from app.modules.asset_groups import tasks
                from app.modules.sightings import tasks as sighting_tasks

                tasks_patch = []
                for func in (
                    'delete_remote',
                    'ensure_remote',
                    'git_push',
                    'sage_detection',
                ):
                    tasks_patch.append(
                        mock.patch.object(
                            getattr(tasks, func),
                            'delay',
                            getattr(tasks, func),
                        ),
                    )
                tasks_patch.append(
                    mock.patch.object(
                        getattr(sighting_tasks, 'send_identification'),
                        'delay',
                        getattr(sighting_tasks, 'send_identification'),
                    ),
                )
                for patch in tasks_patch:
                    patch.start()

            # This is necessary to make celery tasks work when calling
            # in the foreground.  Otherwise there's some weird error:
            #
            # sqlalchemy.orm.exc.DetachedInstanceError: Instance <User
            # at 0x7fe1e592a640> is not bound to a Session; attribute
            # refresh operation cannot proceed (Background on this error
            # at: http://sqlalche.me/e/13/bhk3)
            with mock.patch.object(app, 'app_context', return_value=ctx):
                yield app
            db.drop_all()

            if utils.redis_unavailable():
                for patch in tasks_patch:
                    patch.stop()


@pytest.fixture(scope='session')
def db(flask_app):
    from app.extensions import db as db_instance

    yield db_instance


@pytest.fixture(scope='session')
def temp_db_instance_helper(db):
    def temp_db_instance_manager(instance):
        with db.session.begin():
            db.session.add(instance)

        yield instance

        mapper = instance.__class__.__mapper__
        assert len(mapper.primary_key) == 1
        primary_key = mapper.primary_key[0]
        kwargs = {primary_key.name: mapper.primary_key_from_instance(instance)[0]}
        try:
            instance.__class__.query.filter_by(**kwargs).delete()
        except sqlalchemy.exc.IntegrityError:
            pass
        try:
            instance.__class__.commit()
        except AttributeError:
            pass

    return temp_db_instance_manager


@pytest.fixture(scope='session')
def flask_app_client(flask_app):
    flask_app.test_client_class = utils.AutoAuthFlaskClient
    flask_app.response_class = utils.JSONResponse
    return flask_app.test_client()


@pytest.fixture(scope='session')
def readonly_user(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(email='readonly@localhost')
    ):
        yield _


@pytest.fixture(scope='session')
def user_manager_user(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(
            email='useradmin@localhost',
            is_user_manager=True,
        )
    ):
        yield _


@pytest.fixture(scope='session')
def admin_user(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(
            email='admin@localhost',
            is_admin=True,
        )
    ):
        yield _


@pytest.fixture(scope='session')
def staff_user(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(
            email='staff@localhost',
            is_staff=True,
        )
    ):
        yield _


@pytest.fixture(scope='session')
def regular_user(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(
            email='test@localhost',
        )
    ):
        yield _


@pytest.fixture(scope='session')
def internal_user(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(
            email='internal@localhost',
            is_internal=True,
        )
    ):
        yield _


@pytest.fixture(scope='session')
def researcher_1(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(
            email='researcher1@localhost',
            is_researcher=True,
        )
    ):
        yield _


@pytest.fixture(scope='session')
def data_manager_1(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(
            email='datamanager1@localhost',
            is_data_manager=True,
        )
    ):
        yield _


@pytest.fixture(scope='session')
def data_manager_2(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(
            email='datamanager2@localhost',
            is_data_manager=True,
        )
    ):
        yield _


@pytest.fixture(scope='session')
def contributor_1(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(
            email='contributor1@localhost',
            is_contributor=True,
        )
    ):
        yield _


@pytest.fixture(scope='session')
def researcher_2(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(
            email='researcher2@localhost',
            is_researcher=True,
        )
    ):
        yield _


@pytest.fixture(scope='session')
def temp_user(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(email='temp@localhost', full_name='Temp User')
    ):
        yield _


@pytest.fixture(scope='session')
def collab_user_a(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(email='trout@foo.bar', full_name='Mr Trouty')
    ):
        yield _


@pytest.fixture(scope='session')
def collab_user_b(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(email='salmon@foo.bar', full_name='Mr Salmon')
    ):
        yield _


@pytest.fixture(scope='session')
def encounter_1():
    yield utils.generate_encounter_instance(
        user_email='test1@user', user_password='testuser1', user_full_name='Test User 1'
    )


@pytest.fixture(scope='session')
def encounter_2():
    yield utils.generate_encounter_instance(
        user_email='test2@user', user_password='testuser2', user_full_name='Test User 2'
    )


@pytest.fixture()
def empty_individual():
    from app.modules.individuals.models import Individual

    _individual = Individual()
    return _individual


@pytest.fixture(scope='session')
def test_root(flask_app):
    _test_root = (
        pathlib.Path(flask_app.config.get('PROJECT_ROOT')) / 'tests/asset_groups/test-000'
    )
    return _test_root


def ensure_asset_group_repo(flask_app, db, asset_group, file_data=[]):
    if not utils.is_extension_enabled('gitlab'):
        print('Gitlab unavailable, skip git_push')
        return

    from app.extensions.gitlab import GitlabInitializationError
    from app.modules.asset_groups.tasks import git_push, ensure_remote

    asset_group.ensure_repository()
    # Call ensure_remote without .delay in tests to do it in the foreground
    try:
        ensure_remote(str(asset_group.guid), additional_tags=['type:pytest-required'])
    except GitlabInitializationError:
        print(
            f'Gitlab unavailable, skip ensure_remote for asset group {asset_group.guid}'
        )
    filepath_guid_mapping = {}
    if len(asset_group.assets) == 0:
        for uuid_, path in file_data:
            repo_filepath = asset_group.git_copy_file_add(str(path))
            filepath_guid_mapping[repo_filepath] = uuid_
        asset_group.git_commit(
            'Initial commit for testing',
            existing_filepath_guid_mapping=filepath_guid_mapping,
        )
        # Call git_push without .delay in tests to do it in the foreground
        try:
            git_push(str(asset_group.guid))
        except GitlabInitializationError:
            print(f'Gitlab unavailable, skip git_push for asset group {asset_group.guid}')


@pytest.fixture
def test_asset_group_file_data(test_root):
    return [
        (
            uuid.UUID('00000000-0000-0000-0000-000000000011'),
            test_root / 'zebra.jpg',
        ),
        (
            uuid.UUID('00000000-0000-0000-0000-000000000012'),
            test_root / 'fluke.jpg',
        ),
        (
            uuid.UUID('00000000-0000-0000-0000-000000000013'),
            test_root / 'phoenix.jpg',
        ),
        (
            uuid.UUID('00000000-0000-0000-0000-000000000014'),
            test_root / 'coelacanth.png',
        ),
    ]


@pytest.fixture
def test_asset_group_uuid(flask_app, db, researcher_1, test_asset_group_file_data):
    if not utils.is_extension_enabled('gitlab'):
        print('Gitlab unavailable, skip ensure_asset_group_repo')
        return

    from app.extensions.gitlab import GitlabInitializationError
    from app.modules.asset_groups.models import AssetGroup
    from app.extensions.git_store import GitStoreMajorType as AssetGroupMajorType

    guid = TEST_ASSET_GROUP_UUID
    asset_group = AssetGroup.query.get(guid)
    if asset_group is None:
        asset_group = AssetGroup(
            guid=guid,
            owner_guid=researcher_1.guid,
            major_type=AssetGroupMajorType.test,
            description='This is a required PyTest submission (do not delete)',
        )
        with db.session.begin():
            db.session.add(asset_group)
    else:
        asset_group.owner_guid = researcher_1.guid
        asset_group.major_type = AssetGroupMajorType.test
        asset_group.description = 'This is a required PyTest submission (do not delete)'
        with db.session.begin():
            db.session.merge(asset_group)

    try:
        ensure_asset_group_repo(flask_app, db, asset_group, test_asset_group_file_data)
    except GitlabInitializationError:
        print(f'Gitlab unavailable, skip ensure_asset_group_repo for {asset_group.guid}')
    return asset_group.guid


@pytest.fixture
def test_empty_asset_group_uuid(flask_app, db, researcher_1):
    from app.modules.asset_groups.models import AssetGroup
    from app.extensions.git_store import GitStoreMajorType as AssetGroupMajorType

    guid = TEST_EMPTY_ASSET_GROUP_UUID
    asset_group = AssetGroup.query.get(guid)
    if asset_group is None:
        asset_group = AssetGroup(
            guid=guid,
            owner_guid=researcher_1.guid,
            major_type=AssetGroupMajorType.test,
            description='',
        )
        with db.session.begin():
            db.session.add(asset_group)
    ensure_asset_group_repo(flask_app, db, asset_group)
    return asset_group.guid


@pytest.fixture
def test_clone_asset_group_data(test_asset_group_uuid, test_asset_group_file_data):
    return {
        'asset_group_uuid': test_asset_group_uuid,
        'asset_uuids': [str(f[0]) for f in test_asset_group_file_data],
    }


def ensure_mission_collection_repo(flask_app, db, mission_collection, file_data=[]):
    if not utils.is_extension_enabled('gitlab'):
        print('Gitlab unavailable, skip git_push')
        return

    from app.extensions.gitlab import GitlabInitializationError
    from app.modules.missions.tasks import git_push, ensure_remote

    mission_collection.ensure_repository()
    # Call ensure_remote without .delay in tests to do it in the foreground
    try:
        ensure_remote(
            str(mission_collection.guid), additional_tags=['type:pytest-required']
        )
    except GitlabInitializationError:
        print(
            f'Gitlab unavailable, skip ensure_remote for mission collection {mission_collection.guid}'
        )
    filepath_guid_mapping = {}
    if len(mission_collection.assets) == 0:
        for uuid_, path in file_data:
            repo_filepath = mission_collection.git_copy_file_add(str(path))
            filepath_guid_mapping[repo_filepath] = uuid_
        mission_collection.git_commit(
            'Initial commit for testing',
            existing_filepath_guid_mapping=filepath_guid_mapping,
        )
        # Call git_push without .delay in tests to do it in the foreground
        try:
            git_push(str(mission_collection.guid))
        except GitlabInitializationError:
            print(
                f'Gitlab unavailable, skip git_push for mission collection {mission_collection.guid}'
            )


@pytest.fixture
def test_mission_collection_file_data(test_root):
    return [
        (
            uuid.UUID('00000000-0000-0000-0000-000000000011'),
            test_root / 'zebra.jpg',
        ),
        (
            uuid.UUID('00000000-0000-0000-0000-000000000012'),
            test_root / 'fluke.jpg',
        ),
        (
            uuid.UUID('00000000-0000-0000-0000-000000000013'),
            test_root / 'phoenix.jpg',
        ),
        (
            uuid.UUID('00000000-0000-0000-0000-000000000014'),
            test_root / 'coelacanth.png',
        ),
    ]


@pytest.fixture
def test_mission_collection_uuid(
    flask_app, db, data_manager_1, test_mission_collection_file_data
):
    if not utils.is_extension_enabled('gitlab'):
        print('Gitlab unavailable, skip ensure_mission_collection_repo')
        return

    from app.extensions.gitlab import GitlabInitializationError
    from app.modules.missions.models import MissionCollection
    from app.extensions.git_store import GitStoreMajorType as MissionCollectionMajorType

    guid = TEST_MISSION_COLLECTION_UUID
    mission_collection = MissionCollection.query.get(guid)
    if mission_collection is None:
        mission_collection = MissionCollection(
            guid=guid,
            owner_guid=data_manager_1.guid,
            major_type=MissionCollectionMajorType.test,
            description='This is a required PyTest submission (do not delete)',
        )
        with db.session.begin():
            db.session.add(mission_collection)
    else:
        mission_collection.owner_guid = data_manager_1.guid
        mission_collection.major_type = MissionCollectionMajorType.test
        mission_collection.description = (
            'This is a required PyTest submission (do not delete)'
        )
        with db.session.begin():
            db.session.merge(mission_collection)

    try:
        ensure_mission_collection_repo(
            flask_app, db, mission_collection, test_mission_collection_file_data
        )
    except GitlabInitializationError:
        print(
            f'Gitlab unavailable, skip ensure_mission_collection_repo for {mission_collection.guid}'
        )
    return mission_collection.guid


@pytest.fixture
def test_empty_mission_collection_uuid(flask_app, db, data_manager_1):
    from app.modules.missions.models import MissionCollection
    from app.extensions.git_store import GitStoreMajorType as MissionCollectionMajorType

    guid = TEST_EMPTY_MISSION_COLLECTION_UUID
    mission_collection = MissionCollection.query.get(guid)
    if mission_collection is None:
        mission_collection = MissionCollection(
            guid=guid,
            owner_guid=data_manager_1.guid,
            major_type=MissionCollectionMajorType.test,
            description='',
        )
        with db.session.begin():
            db.session.add(mission_collection)
    ensure_mission_collection_repo(flask_app, db, mission_collection)
    return mission_collection.guid


@pytest.fixture
def test_clone_mission_collection_data(
    test_mission_collection_uuid, test_mission_collection_file_data
):
    return {
        'mission_collection_uuid': test_mission_collection_uuid,
        'asset_uuids': [str(f[0]) for f in test_mission_collection_file_data],
    }


# These are really helpful utils for setting "current_user" in non "resources" tests
@pytest.fixture()
def patch_User_password_scheme():
    from app.modules.users import models

    # pylint: disable=invalid-name,protected-access
    """
    By default, the application uses ``bcrypt`` to store passwords securely.
    However, ``bcrypt`` is a slow hashing algorithm (by design), so it is
    better to downgrade it to ``plaintext`` while testing, since it will save
    us quite some time.
    """
    # NOTE: It seems a hacky way, but monkeypatching is a hack anyway.
    password_field_context = models.User.password.property.columns[0].type.context
    # NOTE: This is used here to forcefully resolve the LazyCryptContext
    password_field_context.context_kwds
    password_field_context._config._init_scheme_list(('plaintext',))
    password_field_context._config._init_records()
    password_field_context._config._init_default_schemes()
    yield
    password_field_context._config._init_scheme_list(('bcrypt',))
    password_field_context._config._init_records()
    password_field_context._config._init_default_schemes()


@pytest.fixture()
def user_instance(patch_User_password_scheme):
    # pylint: invalid-name
    return utils.generate_user_instance()


@pytest.fixture()
def authenticated_user_login(flask_app, user_instance):
    with flask_app.test_request_context('/'):
        login_user(user_instance)
        yield current_user
        logout_user()


@pytest.fixture()
def anonymous_user_login(flask_app):
    with flask_app.test_request_context('/'):
        yield current_user


@pytest.fixture()
def admin_user_login(flask_app, admin_user):
    with flask_app.test_request_context('/'):
        login_user(admin_user)
        yield current_user
        logout_user()


@pytest.fixture()
def user_manager_user_login(flask_app, user_manager_user):
    with flask_app.test_request_context('/'):
        login_user(user_manager_user)
        yield current_user
        logout_user()


@pytest.fixture()
def researcher_1_login(flask_app, researcher_1):
    with flask_app.test_request_context('/'):
        login_user(researcher_1)
        yield current_user
        logout_user()


@pytest.fixture()
def data_manager_1_login(flask_app, data_manager_1):
    with flask_app.test_request_context('/'):
        login_user(data_manager_1)
        yield current_user
        logout_user()


@pytest.fixture()
def contributor_1_login(flask_app, contributor_1):
    with flask_app.test_request_context('/'):
        login_user(contributor_1)
        yield current_user
        logout_user()


@pytest.fixture()
def public_encounter():
    from app.modules.encounters.models import Encounter

    return Encounter(public=True, asset_group_sighting_encounter_guid=uuid.uuid4())


@pytest.fixture()
def owned_encounter(temp_user):
    import tests.utils as test_utils

    return test_utils.generate_owned_encounter(temp_user)
