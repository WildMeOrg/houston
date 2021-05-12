# -*- coding: utf-8 -*-
"""
Asset_group resources utils
-------------
"""
import json
import shutil
import os
import config
from tests import utils as test_utils

PATH = '/api/v1/asset_groups/'


def create_asset_group(flask_app_client, user, data, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('asset_groups:write',)):
        response = flask_app_client.post(
            '%s' % PATH,
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(
            response, 200, {'guid', 'description', 'major_type'}
        )
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def patch_asset_group(
    flask_app_client, user, asset_group_guid, data, expected_status_code=200
):
    with flask_app_client.login(user, auth_scopes=('asset_groups:write',)):
        response = flask_app_client.patch(
            '%s%s' % (PATH, asset_group_guid),
            content_type='application/json',
            data=json.dumps(data),
        )

    if expected_status_code == 200:
        test_utils.validate_dict_response(
            response, 200, {'guid', 'description', 'major_type'}
        )
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_asset_group(flask_app_client, user, asset_group_guid, expected_status_code=200):
    if user:
        with flask_app_client.login(user, auth_scopes=('asset_groups:read',)):
            response = flask_app_client.get('%s%s' % (PATH, asset_group_guid))
    else:
        response = flask_app_client.get('%s%s' % (PATH, asset_group_guid))
    if expected_status_code == 200:
        test_utils.validate_dict_response(
            response, 200, {'guid', 'description', 'major_type'}
        )
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def read_all_asset_groups(flask_app_client, user, expected_status_code=200):
    with flask_app_client.login(user, auth_scopes=('asset_groups:read',)):
        response = flask_app_client.get(PATH)

    if expected_status_code == 200:
        test_utils.validate_list_response(response, 200)
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )
    return response


def delete_asset_group(
    flask_app_client, user, asset_group_guid, expected_status_code=204
):
    with flask_app_client.login(user, auth_scopes=('asset_groups:write',)):
        response = flask_app_client.delete('%s%s' % (PATH, asset_group_guid))

    if expected_status_code == 204:
        assert response.status_code == 204
    else:
        test_utils.validate_dict_response(
            response, expected_status_code, {'status', 'message'}
        )


# multiple tests clone a asset_group, do something with it and clean it up. Make sure this always happens using a
# class with a cleanup method to be called if any assertions fail
class CloneAssetGroup(object):
    def __init__(self, client, admin_user, owner, guid, force_clone):
        from app.modules.asset_groups.models import AssetGroup

        self.asset_group = None
        self.guid = guid

        # Allow the option of forced cloning, this could raise an exception if the assertion fails
        # but this does not need to be in any try/except/finally construct as no resources are allocated yet
        if force_clone:
            database_path = config.TestingConfig.ASSET_GROUP_DATABASE_PATH
            asset_group_path = os.path.join(database_path, str(guid))

            if os.path.exists(asset_group_path):
                shutil.rmtree(asset_group_path)
            assert not os.path.exists(asset_group_path)

        url = f'{PATH}{guid}'
        with client.login(owner, auth_scopes=('asset_groups:read',)):
            self.response = client.get(url)

        # only store the asset_group if the clone worked
        if self.response.status_code == 200:
            self.asset_group = AssetGroup.query.get(self.response.json['guid'])

        elif self.response.status_code in (428, 403):
            # 428 Precondition Required
            # 403 Forbidden
            with client.login(admin_user, auth_scopes=('asset_groups:write',)):
                self.response = client.post(url)

            # only store the asset_group if the clone worked
            if self.response.status_code == 200:
                self.asset_group = AssetGroup.query.get(self.response.json['guid'])

            # reassign ownership
            data = [
                test_utils.patch_add_op('owner', '%s' % owner.guid),
            ]
            patch_asset_group(client, admin_user, guid, data)
            # and read it back as the real user
            with client.login(owner, auth_scopes=('asset_groups:read',)):
                self.response = client.get(url)

    def remove_files(self):
        database_path = config.TestingConfig.ASSET_GROUP_DATABASE_PATH
        asset_group_path = os.path.join(database_path, str(self.guid))
        if os.path.exists(asset_group_path):
            shutil.rmtree(asset_group_path)

    def cleanup(self):
        # Restore original state
        if self.asset_group is not None:
            self.asset_group.delete()
            self.asset_group = None
        self.remove_files()


# Clone the asset_group
def clone_asset_group(
    client,
    admin_user,
    owner,
    guid,
    force_clone=False,
    expect_failure=False,
):
    clone = CloneAssetGroup(client, admin_user, owner, guid, force_clone)

    if not expect_failure:
        assert clone.response.status_code == 200
    return clone
