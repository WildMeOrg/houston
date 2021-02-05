# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import json

from tests.extensions.config import utils
from tests import utils as test_utils


def _patch_request(flask_app_client, data):
    response = flask_app_client.patch(
        '/api/v1/config/houston/',
        content_type='application/json',
        data=json.dumps(data),
    )
    return response


def test_modifying_db_config_by_regular_user(flask_app_client, regular_user, db):
    try:
        utils.get_and_check_houston_configs()  # Ensure an empty database of existing configs

        with flask_app_client.login(regular_user, auth_scopes=('config.houston:write',)):
            data = [
                test_utils.patch_test_op(regular_user.password_secret),
                test_utils.patch_add_op('ENV', 'testing-with-db'),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.status_code == 403
            assert response.content_type == 'application/json'
            assert isinstance(response.json, dict)
            assert set(response.json.keys()) >= {'status', 'message'}

            utils.get_and_check_houston_configs()  # Ensure an empty database of existing configs
    except Exception as ex:
        raise ex
    finally:
        utils.delete_all_houston_configs(db)


def test_modifying_db_config_by_admin(flask_app_client, staff_user, db):
    # pylint: disable=invalid-name
    try:
        utils.get_and_check_houston_configs()  # Ensure an empty database of existing configs

        new_env = 'testing-with-db'

        with flask_app_client.login(staff_user, auth_scopes=('config.houston:write',)):
            data = [
                test_utils.patch_test_op(staff_user.password_secret),
                test_utils.patch_add_op('ENV', new_env),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils.get_and_check_houston_configs(key='ENV', value=new_env)

            data = [
                test_utils.patch_test_op(staff_user.password_secret),
                test_utils.patch_remove_op(path='ENV'),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils.get_and_check_houston_configs()
    except Exception as ex:
        raise ex
    finally:
        utils.delete_all_houston_configs(db)


def test_modifying_db_config_by_admin_with_invalid_password_must_fail(
    flask_app_client, staff_user, db
):
    # pylint: disable=invalid-name
    try:
        utils.get_and_check_houston_configs()  # Ensure an empty database of existing configs

        new_env = 'testing-with-db'

        with flask_app_client.login(staff_user, auth_scopes=('config.houston:write',)):
            data = [
                test_utils.patch_test_op('invalid_password'),
                test_utils.patch_add_op('ENV', new_env),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.status_code == 403
            assert response.content_type == 'application/json'
            assert isinstance(response.json, dict)
            assert set(response.json.keys()) >= {'status', 'message'}

            utils.get_and_check_houston_configs()  # Ensure an empty database of existing configs
    except Exception as ex:
        raise ex
    finally:
        utils.delete_all_houston_configs(db)


def test_modifying_db_config_by_admin_with_idempotence(flask_app_client, staff_user, db):
    # pylint: disable=invalid-name
    try:
        utils.get_and_check_houston_configs()  # Ensure an empty database of existing configs

        new_env = 'testing-with-db'

        with flask_app_client.login(staff_user, auth_scopes=('config.houston:write',)):
            data = [
                test_utils.patch_test_op(staff_user.password_secret),
                test_utils.patch_add_op('ENV', new_env),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils.get_and_check_houston_configs(key='ENV', value=new_env)

            # Send the exact same request
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils.get_and_check_houston_configs(key='ENV', value=new_env)

            # Send the same request but send two add ops for the same path
            data = data + [data[-1]]
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils.get_and_check_houston_configs(key='ENV', value=new_env)

            data = [
                test_utils.patch_test_op(staff_user.password_secret),
                test_utils.patch_remove_op(path='ENV'),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils.get_and_check_houston_configs()

            # Send the exact same request
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils.get_and_check_houston_configs()

            # Send the same request but send two remove ops for the same path
            data = data + [data[-1]]
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils.get_and_check_houston_configs()

    except Exception as ex:
        raise ex
    finally:
        utils.delete_all_houston_configs(db)


def test_modifying_db_config_by_admin_with_batch(flask_app_client, staff_user, db):
    # pylint: disable=invalid-name
    try:
        utils.get_and_check_houston_configs()  # Ensure an empty database of existing configs

        new_env = 'testing-with-db'

        with flask_app_client.login(staff_user, auth_scopes=('config.houston:write',)):
            data = [
                test_utils.patch_test_op(staff_user.password_secret),
                test_utils.patch_add_op('ENV', new_env),
                test_utils.patch_remove_op(path='ENV'),
                test_utils.patch_add_op('ENV', new_env),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils.get_and_check_houston_configs(key='ENV', value=new_env)
    except Exception as ex:
        raise ex
    finally:
        utils.delete_all_houston_configs(db)


def test_modifying_nonexistent_db_config_by_admin(flask_app_client, staff_user, db):
    # pylint: disable=invalid-name
    try:
        utils.get_and_check_houston_configs()  # Ensure an empty database of existing configs

        with flask_app_client.login(staff_user, auth_scopes=('config.houston:write',)):
            data = [
                test_utils.patch_test_op(staff_user.password_secret),
                test_utils.patch_add_op('CONFIG_DOES_NOT_EXIST', 'invalid_config'),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.status_code == 422
            assert response.content_type == 'application/json'
            assert isinstance(response.json, dict)
            assert set(response.json.keys()) >= {'status', 'message'}

            utils.get_and_check_houston_configs()  # Ensure an empty database of existing configs
    except Exception as ex:
        raise ex
    finally:
        utils.delete_all_houston_configs(db)


def test_modifying_db_config_by_admin_with_bad_value(flask_app_client, staff_user, db):
    # pylint: disable=invalid-name
    try:
        utils.get_and_check_houston_configs()  # Ensure an empty database of existing configs

        with flask_app_client.login(staff_user, auth_scopes=('config.houston:write',)):
            data = [
                test_utils.patch_test_op(staff_user.password_secret),
                test_utils.patch_add_op('ENV', None),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.status_code == 422
            assert response.content_type == 'application/json'
            assert isinstance(response.json, dict)
            assert set(response.json.keys()) >= {'status', 'message'}

            utils.get_and_check_houston_configs()  # Ensure an empty database of existing configs
    except Exception as ex:
        raise ex
    finally:
        utils.delete_all_houston_configs(db)
