# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
import json

from tests.extensions.config import utils


def _patch_request(flask_app_client, data):
    response = flask_app_client.patch(
        '/api/v1/config/houston/',
        content_type='application/json',
        data=json.dumps(data),
    )
    return response


def _test_op(value):
    return {
        'op': 'test',
        'path': '/current_password',
        'value': value,
    }


def _add_op(value, path='ENV'):
    return {
        'op': 'add',
        'path': '/%s' % (path,),
        'value': value,
    }


def _remove_op(path='ENV'):
    return {
        'op': 'remove',
        'path': '/%s' % (path,),
    }


def test_modifying_db_config_by_regular_user(flask_app_client, regular_user, db):
    try:
        utils._get_and_check_houston_configs()  # Ensure an empty database of existing configs

        with flask_app_client.login(regular_user, auth_scopes=('config.houston:write',)):
            data = [
                _test_op(regular_user.password_secret),
                _add_op('testing-with-db'),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.status_code == 403
            assert response.content_type == 'application/json'
            assert isinstance(response.json, dict)
            assert set(response.json.keys()) >= {'status', 'message'}

            utils._get_and_check_houston_configs()  # Ensure an empty database of existing configs
    except Exception as ex:
        raise ex
    finally:
        utils._delete_all_houston_configs(db)


def test_modifying_db_config_by_admin(flask_app_client, admin_user, db):
    # pylint: disable=invalid-name
    try:
        utils._get_and_check_houston_configs()  # Ensure an empty database of existing configs

        new_env = 'testing-with-db'

        with flask_app_client.login(admin_user, auth_scopes=('config.houston:write',)):
            data = [
                _test_op(admin_user.password_secret),
                _add_op(new_env),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils._get_and_check_houston_configs(key='ENV', value=new_env)

            data = [
                _test_op(admin_user.password_secret),
                _remove_op(path='ENV'),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils._get_and_check_houston_configs()
    except Exception as ex:
        raise ex
    finally:
        utils._delete_all_houston_configs(db)


def test_modifying_db_config_by_admin_with_invalid_password_must_fail(
    flask_app_client, admin_user, db
):
    # pylint: disable=invalid-name
    try:
        utils._get_and_check_houston_configs()  # Ensure an empty database of existing configs

        new_env = 'testing-with-db'

        with flask_app_client.login(admin_user, auth_scopes=('config.houston:write',)):
            data = [
                _test_op('invalid_password'),
                _add_op(new_env),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.status_code == 403
            assert response.content_type == 'application/json'
            assert isinstance(response.json, dict)
            assert set(response.json.keys()) >= {'status', 'message'}

            utils._get_and_check_houston_configs()  # Ensure an empty database of existing configs
    except Exception as ex:
        raise ex
    finally:
        utils._delete_all_houston_configs(db)


def test_modifying_db_config_by_admin_with_idempotence(flask_app_client, admin_user, db):
    # pylint: disable=invalid-name
    try:
        utils._get_and_check_houston_configs()  # Ensure an empty database of existing configs

        new_env = 'testing-with-db'

        with flask_app_client.login(admin_user, auth_scopes=('config.houston:write',)):
            data = [
                _test_op(admin_user.password_secret),
                _add_op(new_env),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils._get_and_check_houston_configs(key='ENV', value=new_env)

            # Send the exact same request
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils._get_and_check_houston_configs(key='ENV', value=new_env)

            # Send the same request but send two add ops for the same path
            data = data + [data[-1]]
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils._get_and_check_houston_configs(key='ENV', value=new_env)

            data = [
                _test_op(admin_user.password_secret),
                _remove_op(path='ENV'),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils._get_and_check_houston_configs()

            # Send the exact same request
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils._get_and_check_houston_configs()

            # Send the same request but send two remove ops for the same path
            data = data + [data[-1]]
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils._get_and_check_houston_configs()

    except Exception as ex:
        raise ex
    finally:
        utils._delete_all_houston_configs(db)


def test_modifying_db_config_by_admin_with_batch(flask_app_client, admin_user, db):
    # pylint: disable=invalid-name
    try:
        utils._get_and_check_houston_configs()  # Ensure an empty database of existing configs

        new_env = 'testing-with-db'

        with flask_app_client.login(admin_user, auth_scopes=('config.houston:write',)):
            data = [
                _test_op(admin_user.password_secret),
                _add_op(new_env),
                _remove_op(path='ENV'),
                _add_op(new_env),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.json
            utils._get_and_check_houston_configs(key='ENV', value=new_env)
    except Exception as ex:
        raise ex
    finally:
        utils._delete_all_houston_configs(db)


def test_modifying_nonexistent_db_config_by_admin(flask_app_client, admin_user, db):
    # pylint: disable=invalid-name
    try:
        utils._get_and_check_houston_configs()  # Ensure an empty database of existing configs

        with flask_app_client.login(admin_user, auth_scopes=('config.houston:write',)):
            data = [
                _test_op(admin_user.password_secret),
                _add_op('invalid_config', path='CONFIG_DOES_NOT_EXIST'),
            ]
            response = _patch_request(flask_app_client, data)

            assert response.status_code == 422
            assert response.content_type == 'application/json'
            assert isinstance(response.json, dict)
            assert set(response.json.keys()) >= {'status', 'message'}

            utils._get_and_check_houston_configs()  # Ensure an empty database of existing configs
    except Exception as ex:
        raise ex
    finally:
        utils._delete_all_houston_configs(db)


def test_modifying_db_config_by_admin_with_bad_value(flask_app_client, admin_user, db):
    # pylint: disable=invalid-name
    try:
        utils._get_and_check_houston_configs()  # Ensure an empty database of existing configs

        with flask_app_client.login(admin_user, auth_scopes=('config.houston:write',)):
            data = [_test_op(admin_user.password_secret), _add_op(None)]
            response = _patch_request(flask_app_client, data)

            assert response.status_code == 422
            assert response.content_type == 'application/json'
            assert isinstance(response.json, dict)
            assert set(response.json.keys()) >= {'status', 'message'}

            utils._get_and_check_houston_configs()  # Ensure an empty database of existing configs
    except Exception as ex:
        raise ex
    finally:
        utils._delete_all_houston_configs(db)
