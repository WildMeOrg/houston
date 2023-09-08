# -*- coding: utf-8 -*-
import logging
import os
import pathlib
import shutil
import tempfile
import time
import uuid
import warnings
from importlib import import_module
from unittest import mock

import pytest
import sqlalchemy
from flask_login import current_user, login_user, logout_user

from app import create_app
from app.extensions.tus import tus_upload_dir
from config import CONTEXT_ENVIRONMENT_VARIABLE, VALID_CONTEXTS
from flask_restx_patched import is_extension_enabled, is_module_enabled

from . import TEST_ASSET_GROUP_UUID, TEST_EMPTY_ASSET_GROUP_UUID, utils

log = logging.getLogger('pytest.conftest')  # pylint: disable=invalid-name

# So that every single util does not need to be passed the flask_config to get stuff, read it all at test startup
# and have it accessible from here. Populated in  create_test_data autouse function below
test_config = {}

# Force FLASK_ENV to be testing instead of using what's defined in the environment
os.environ['FLASK_ENV'] = 'testing'
# Remove MAIL_DEFAULT_SENDER_EMAIL environment variable so the generated
# one is used in tests
if 'MAIL_DEFAULT_SENDER_EMAIL' in os.environ:
    del os.environ['MAIL_DEFAULT_SENDER_EMAIL']


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
    parser.addoption(
        '--no-elasticsearch',
        action='store_true',
        default=False,
        help=('Disable Elasticsearch with tests'),
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

    if 'disable_elasticsearch' in metafunc.fixturenames:
        value = metafunc.config.option.no_elasticsearch
        value = [value]
        metafunc.parametrize('disable_elasticsearch', value, scope='session')


@pytest.fixture(autouse=True)
def check_cleanup_objects(db):
    count = utils.all_count(db)
    yield
    assert count == utils.all_count(
        db
    ), 'Some objects created in the test need to be cleaned up'


@pytest.fixture(autouse=True)
def cleanup_objects(db, flask_app):
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

    upload_dir = tus_upload_dir(flask_app)
    for path in pathlib.Path(upload_dir).glob('./*'):
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


@pytest.fixture(autouse=True)
def email_setup(flask_app):
    from app.modules.site_settings.models import SiteSetting

    # this should only run in TESTING (non-sending) mode
    assert flask_app.testing
    flask_app.config['MAIL_OVERRIDE_RECIPIENTS'] = None

    # this mocks using mailchimp, but wont send since we are in TESTING
    SiteSetting.set_key_value('email_service', 'mailchimp')
    SiteSetting.set_key_value('email_service_username', 'testing_' + str(uuid.uuid4()))
    SiteSetting.set_key_value('email_service_password', 'testing_' + str(uuid.uuid4()))

    yield

    # gets rid of system_guid as well (important for other tests)
    SiteSetting.query.delete()


# Needs to be an autouse to ensure that these are actually created. Any user can read them but only admin can create
@pytest.fixture(autouse=True)
def create_test_data(db, flask_app_client, admin_user):
    import tests.modules.site_settings.resources.utils as site_setting_utils

    test_config['regions'] = site_setting_utils.get_and_ensure_test_regions(
        flask_app_client, admin_user
    )

    taxonomy = site_setting_utils.get_some_taxonomy_dict(flask_app_client, admin_user)
    test_config['taxonomy_guid'] = taxonomy['id']
    yield
    # Do not remove afterwards as not supported


@pytest.fixture(scope='session')
def flask_app(gitlab_remote_login_pat, disable_elasticsearch):

    if is_extension_enabled('elasticsearch'):
        from app.extensions import elasticsearch as es
    else:
        es = None

    if disable_elasticsearch:
        if es is not None:
            es.off()
        es = None

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
        config_override['UPLOADS_DATABASE_PATH'] = str(pathlib.Path(td) / 'uploads')
        config_override['FILEUPLOAD_BASE_PATH'] = str(pathlib.Path(td) / 'fileuploads')

        # Override values that might be defined in docker-compose.override.yml
        config_override['DEFAULT_EMAIL_SERVICE_USERNAME'] = None
        config_override['DEFAULT_EMAIL_SERVICE_PASSWORD'] = None
        config_override['RECAPTCHA_PUBLIC_KEY'] = None
        config_override['SERVER_NAME'] = 'localhost:84'

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

            # Delete all content in all tables (may be left over from previous tests after an error)
            if es is not None:
                with db.session.begin():
                    for table in reversed(db.metadata.sorted_tables):
                        log.info('Delete DB table %s' % table)
                        db.session.execute(table.delete())

            if utils.redis_unavailable():
                # Run code in foreground if redis not available
                from app.extensions.git_store import tasks as git_store_tasks

                tasks_patch = []
                for func in (
                    'delete_remote',
                    'ensure_remote',
                    # 'git_commit',
                    'git_push',
                ):
                    tasks_patch.append(
                        mock.patch.object(
                            getattr(git_store_tasks, func),
                            'delay',
                            getattr(git_store_tasks, func),
                        ),
                    )

                for patch in tasks_patch:
                    patch.start()

            # initialize Elastic search indexes
            if es is not None:
                es.attach_listeners(app)

                # Update indices
                update = app.config.get('ELASTICSEARCH_BUILD_INDEX_ON_STARTUP', False)
                es.es_index_all(app, pit=True, update=update, force=True)

            # This is necessary to make celery tasks work when calling
            # in the foreground.  Otherwise there's some weird error:
            #
            # sqlalchemy.orm.exc.DetachedInstanceError: Instance <User
            # at 0x7fe1e592a640> is not bound to a Session; attribute
            # refresh operation cannot proceed (Background on this error
            # at: http://sqlalche.me/e/13/bhk3)
            with mock.patch.object(app, 'app_context', return_value=ctx):
                yield app

            # Drop all data from elasticsearch
            if es is not None:
                # Ensure that Elasticsearch is enabled
                es.on()

                # Ensure that any background Celery tasks have wrapped up
                es.check_celery(revoke=True)

                for count in range(10):
                    num_active = es.check_celery()
                    if num_active == 0:
                        break
                    time.sleep(1)

                # Kill any jobs still pending after 10 seconds
                es.shutdown_celery()

                # Delete all content in all tables
                # (we need to do this to know what data to delete out of elastic search)
                with db.session.begin():
                    for table in reversed(db.metadata.sorted_tables):
                        log.info('Delete DB table %s' % table)
                        db.session.execute(table.delete())

                # Delete all content in elasticsearch
                with es.session.begin(blocking=True, verify=True):
                    es.es_index_all(app, update=False)

                indices = es.es_all_indices()
                for index in indices:
                    if index.startswith(es.TESTING_PREFIX):
                        log.debug('Cleaning up test index {!r}'.format(index))
                        es.es_delete_index(index, app=app)

            # Drop all tables
            db.drop_all()

            # Delete all patched tasks
            if utils.redis_unavailable():
                for patch in tasks_patch:
                    patch.stop()


@pytest.fixture(scope='session')
def db(flask_app):
    from app.extensions import db as db_instance

    # Always error on SADeprecationWarnings when testing
    warnings.filterwarnings('error', category=sqlalchemy.exc.SADeprecationWarning)
    warnings.filterwarnings('error', category=ResourceWarning)

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
            password='Pas$w0rd',
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
def exporter(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(
            email='exporter@localhost',
            is_exporter=True,
        )
    ):
        yield _


@pytest.fixture(scope='session')
def admin_user_2(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(
            email='adminuser2@localhost',
            is_admin=True,
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

    from app.extensions.git_store.tasks import ensure_remote, git_push
    from app.extensions.gitlab import GitlabInitializationError

    asset_group.ensure_repository()
    # Call ensure_remote without .delay in tests to do it in the foreground

    try:
        ensure_remote(str(asset_group.guid), additional_tags=['type:pytest-required'])
    except GitlabInitializationError:
        print(
            f'Gitlab unavailable, skip ensure_remote for asset group {asset_group.guid}'
        )

    filepath_guid_mapping = {}
    input_files = []
    if len(asset_group.assets) == 0:
        for uuid_, path in file_data:
            repo_filepath = asset_group.git_copy_file_add(str(path))
            filepath_guid_mapping[repo_filepath] = uuid_
            input_files.append(os.path.basename(path))
        asset_group.git_commit(
            'Initial commit for testing',
            existing_filepath_guid_mapping=filepath_guid_mapping,
            input_filenames=input_files,
            update=True,
            commit=True,
        )
        asset_group.post_preparation_hook()

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

    from app.extensions.git_store import GitStoreMajorType as AssetGroupMajorType
    from app.extensions.gitlab import GitlabInitializationError
    from app.modules.asset_groups.models import AssetGroup

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
    from app.extensions.git_store import GitStoreMajorType as AssetGroupMajorType
    from app.modules.asset_groups.models import AssetGroup

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
def admin_user_login_2(flask_app, admin_user_2):
    with flask_app.test_request_context('/'):
        login_user(admin_user_2)
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
    import tests.utils as test_utils
    from app.modules.users.models import User

    return test_utils.generate_owned_encounter(User.get_public_user())


@pytest.fixture()
def owned_encounter(temp_user):
    import tests.utils as test_utils

    return test_utils.generate_owned_encounter(temp_user)
