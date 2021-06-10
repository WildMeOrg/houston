# -*- coding: utf-8 -*-
import pathlib
import tempfile
import uuid
from unittest import mock

import sqlalchemy
import pytest
from flask_login import current_user, login_user, logout_user
from tests import utils

from app import create_app


def pytest_addoption(parser):
    parser.addoption(
        '--gitlab-remote-login-pat',
        action='append',
        default=[],
        help=('Specify additional config argument for GitLab'),
    )


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
        config_override['ASSET_DATABASE_PATH'] = str(pathlib.Path(td) / 'assets')
        config_override['UPLOADS_DATABASE_PATH'] = str(pathlib.Path(td) / 'uploads')
        config_override['FILEUPLOAD_BASE_PATH'] = str(pathlib.Path(td) / 'fileuploads')
        config_override['SQLALCHEMY_DATABASE_PATH'] = str(
            pathlib.Path(td) / 'database.sqlite3'
        )

        app = create_app(flask_config_name='testing', config_override=config_override)
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

                tasks_patch = []
                tasks_patch.append(
                    mock.patch.object(
                        tasks.delete_remote,
                        'delay',
                        lambda *args, **kwargs: tasks.delete_remote(*args, **kwargs),
                    )
                )
                tasks_patch.append(
                    mock.patch.object(
                        tasks.ensure_remote,
                        'delay',
                        lambda *args, **kwargs: tasks.ensure_remote(*args, **kwargs),
                    )
                )
                tasks_patch.append(
                    mock.patch.object(
                        tasks.git_push,
                        'delay',
                        lambda *args, **kwargs: tasks.git_push(*args, **kwargs),
                    )
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
    from app.extensions.gitlab import GitlabInitializationError
    from app.modules.asset_groups.tasks import git_push, ensure_remote

    repo = asset_group.get_repository()
    if repo:
        # repo already exists
        return

    with db.session.begin():
        db.session.add(asset_group)
    db.session.refresh(asset_group)
    asset_group.ensure_repository()
    # Call ensure_remote without .delay in tests to do it in the foreground
    try:
        ensure_remote(str(asset_group.guid), additional_tags=['type:pytest-required'])
    except GitlabInitializationError:
        print(
            f'gitlab unavailable, skip ensure_remote for asset group {asset_group.guid}'
        )
    filepath_guid_mapping = {}
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
        print(f'gitlab unavailable, skip git_push for asset group {asset_group.guid}')


@pytest.fixture(scope='session')
def test_asset_group_uuid(flask_app, db, test_root, admin_user):
    from app.extensions.gitlab import GitlabInitializationError
    from app.modules.asset_groups.models import AssetGroup, AssetGroupMajorType

    asset_group = AssetGroup(
        guid='00000000-0000-0000-0000-000000000003',
        owner_guid=admin_user.guid,
        major_type=AssetGroupMajorType.test,
        description='This is a required PyTest submission (do not delete)',
    )

    file_data = [
        (
            uuid.UUID('00000000-0000-0000-0000-000000000011'),
            test_root / 'zebra.jpg',
        ),
        (
            uuid.UUID('00000000-0000-0000-0000-000000000012'),
            test_root / 'fluke.jpg',
        ),
    ]
    try:
        ensure_asset_group_repo(flask_app, db, asset_group, file_data)
    except GitlabInitializationError:
        print(f'gitlab unavailable, skip ensure_asset_group_repo for {asset_group.guid}')
    return asset_group.guid


@pytest.fixture(scope='session')
def test_empty_asset_group_uuid(flask_app, db, admin_user):
    from app.modules.asset_groups.models import AssetGroup, AssetGroupMajorType

    asset_group = AssetGroup(
        guid='00000000-0000-0000-0000-000000000001',
        owner_guid=admin_user.guid,
        major_type=AssetGroupMajorType.test,
        description='',
    )
    ensure_asset_group_repo(flask_app, db, asset_group)
    return asset_group.guid


@pytest.fixture(scope='session')
def test_clone_asset_group_data(test_asset_group_uuid):
    return {
        'asset_group_uuid': test_asset_group_uuid,
        'asset_uuids': [
            '00000000-0000-0000-0000-000000000011',
            '00000000-0000-0000-0000-000000000012',
        ],
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
def contributor_1_login(flask_app, contributor_1):
    with flask_app.test_request_context('/'):
        login_user(contributor_1)
        yield current_user
        logout_user()


@pytest.fixture()
def public_encounter():
    from app.modules.encounters.models import Encounter

    return Encounter(public=True)


@pytest.fixture()
def owned_encounter(temp_user):
    from app.modules.encounters.models import Encounter

    return Encounter(owner_guid=temp_user.guid, owner=temp_user)
