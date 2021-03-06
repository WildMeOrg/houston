# -*- coding: utf-8 -*-
import sqlalchemy
import pytest
import uuid

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
def admin_user(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(
            email='admin@localhost',
            is_admin=True,
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
def temp_user(temp_db_instance_helper):
    for _ in temp_db_instance_helper(
        utils.generate_user_instance(email='temp@localhost', full_name='Temp User')
    ):
        yield _


@pytest.fixture(scope='session')
def test_submission_uuid(flask_app):
    return uuid.UUID('ce91ad6e-3cc9-48e8-a4f0-ac74f55dfbf0')


@pytest.fixture(scope='session')
def test_empty_submission_uuid(flask_app):
    return uuid.UUID('ce91ad6e-3cc9-48e8-a4f0-ac74f55dfbf1')


@pytest.fixture(scope='session')
def test_clone_submission_data(flask_app):
    return {
        'submission_uuid': '290950fb-49a8-496a-adf4-e925010f79ce',
        'asset_uuids': [
            '3abc03a8-39c8-42c4-bedb-e08ccc485396',
            'aee00c38-137e-4392-a4d9-92b545a9efb0',
        ],
    }
