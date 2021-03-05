# -*- coding: utf-8 -*-
import sqlalchemy
import pytest
import uuid
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

    config_override = {}
    if gitlab_remote_login_pat is not None:
        config_override['GITLAB_REMOTE_LOGIN_PAT'] = gitlab_remote_login_pat

    app = create_app(flask_config_name='testing', config_override=config_override)
    from app.extensions import db

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


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
def test_submission_uuid(flask_app):
    return uuid.UUID('6e50ece6-742b-4496-bff6-b2c575db3c13')


@pytest.fixture(scope='session')
def test_empty_submission_uuid(flask_app):
    return uuid.UUID('610a0324-1543-42d6-a7b7-1e488cf7ea69')


@pytest.fixture(scope='session')
def test_clone_submission_data(flask_app):
    return {
        'submission_uuid': '6e50ece6-742b-4496-bff6-b2c575db3c13',
        'asset_uuids': [
            'cb4ff916-8a7f-4f2d-97dc-633c716ee072',
            'eefff2e0-292f-4874-9258-a069694fdd0d',
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
