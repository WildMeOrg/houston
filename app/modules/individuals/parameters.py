# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Individuals resources RESTful API
-----------------------------------------------------------
"""
from flask_restx_patched import Parameters, PatchJSONParameters
from . import schemas
import logging
import app.modules.utils as util
from flask_restx_patched._http import HTTPStatus
from flask_marshmallow import base_fields
from app.utils import HoustonException
from uuid import UUID


log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class CreateIndividualParameters(Parameters, schemas.DetailedIndividualSchema):
    names = base_fields.List(
        base_fields.Raw(),
        description='List of Individual Names',
        required=False,
    )

    class Meta(schemas.DetailedIndividualSchema.Meta):
        pass


class PatchIndividualDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REMOVE,
    )

    PATH_CHOICES_EDM = (
        '/encounters',
        '/sex',
        '/timeOfBirth',
        '/timeOfDeath',
        '/comments',
        '/customFields',
    )

    PATH_CHOICES_HOUSTON = ('/featuredAssetGuid', '/encounters', '/names')

    PATH_CHOICES = PATH_CHOICES_EDM + PATH_CHOICES_HOUSTON

    @classmethod
    def remove(cls, obj, field, value, state):
        ret_val = False
        if field == 'encounters':
            for encounter_guid in value:
                from app.modules.encounters.models import Encounter

                encounter = Encounter.query.get(encounter_guid)
                if encounter is not None and encounter in obj.encounters:
                    obj.remove_encounter(encounter)
                    ret_val = True
        elif field == 'featuredAssetGuid' and util.is_valid_uuid_string(value):
            obj.set_featured_asset_guid(UUID(value, version=4))
            ret_val = True
        elif (
            field == 'names'
            and isinstance(value, str)
            and util.is_valid_uuid_string(value)
        ):
            from app.modules.names.models import Name

            name = Name.query.get(value)
            if not name or name.individual_guid != obj.guid:
                raise HoustonException(
                    log,
                    f'invalid name guid {value}',
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                )
            try:
                obj.remove_name(name)
            except ValueError as ve:
                raise HoustonException(
                    log,
                    f'{name} could not be removed from {obj}: {str(ve)}',
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                )
            ret_val = True

        # special case for removing user from preferring_users:  value={preferring_user: user_guid}
        elif (
            field == 'names'
            and isinstance(value, dict)
            and {'guid', 'preferring_user'} == set(value.keys())
            and util.is_valid_uuid_string(value['guid'])
            and util.is_valid_uuid_string(value['preferring_user'])
        ):
            from app.modules.names.models import Name
            from app.modules.users.models import User
            from flask_login import current_user

            name = Name.query.get(value['guid'])
            if not name or name.individual_guid != obj.guid:
                raise HoustonException(
                    log,
                    code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    message=f"invalid name guid {value['guid']}",
                )
            user = User.query.get(value['preferring_user'])
            # decree from 2021-12-08 slack discussion is user can only add/remove self
            #   but this can be rolled back by dropping second part of this conditional
            if not user or user != current_user:
                raise HoustonException(
                    log,
                    f"invalid user guid {value['preferring_user']}",
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                )
            found = name.remove_preferring_user(user)
            return found

        return ret_val

    @classmethod
    def add(cls, obj, field, value, state):
        # there are two forms for op=add path=/names:
        # 1. ADD NEW NAME:  value = {context: C, value: V, preferring_users: [user_guid...]}   (preferring_users is optional)
        # 2. ADD NEW PREFERRING USER (existing name):  value = {guid: name_guid, preferring_user: user_guid}
        if field == 'names':  # add and replace are diff for names
            if not isinstance(value, dict) or (
                not set(value.keys()) >= {'context', 'value'}
                and set(value.keys()) != {'guid', 'preferring_user'}
            ):
                raise HoustonException(
                    log,
                    'value must contain keys ("context", "value") or ("guid", "preferring_user")',
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                )
            from app.modules.names.models import Name
            from app.modules.users.models import User
            from flask_login import current_user

            if 'context' in value:
                # if add_name fails (e.g. constraint violation due to context duplication) a 409/conflict will be returned
                preferring_users = []
                if 'preferring_users' in value and isinstance(
                    value['preferring_users'], list
                ):
                    for user_guid in value['preferring_users']:
                        user = User.query.get(user_guid)
                        # see above decree from 2021-12-08
                        if not user or user != current_user:
                            raise HoustonException(
                                log,
                                f'invalid user guid {user_guid}',
                                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                            )
                        preferring_users.append(user)
                obj.add_name(
                    value['context'], value['value'], current_user, preferring_users
                )
                return True
            else:
                name = Name.query.get(value['guid'])
                if not name or name.individual_guid != obj.guid:
                    raise HoustonException(
                        log,
                        f"invalid name guid {value['guid']}",
                        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    )
                user = User.query.get(value['preferring_user'])
                # see above decree from 2021-12-08
                if not user or user != current_user:
                    raise HoustonException(
                        log,
                        f"invalid user guid {value['preferring_user']}",
                        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    )
                name.add_preferring_user(user)
                return True

        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):
        ret_val = False
        if field == 'encounters':
            for encounter_guid in value:
                from app.modules.encounters.models import Encounter

                encounter = Encounter.query.get(encounter_guid)
                if encounter is not None and encounter not in obj.encounters:
                    obj.add_encounter(encounter)
                    assert encounter in obj.get_encounters()
                    ret_val = True

        elif field == 'featuredAssetGuid' and util.is_valid_uuid_string(value):
            ret_val = obj.set_featured_asset_guid(UUID(value, version=4))
        elif field == 'names':
            from app.modules.names.models import Name

            if (
                not isinstance(value, dict)
                or 'guid' not in value.keys()
                or not util.is_valid_uuid_string(value['guid'])
                or ('context' not in value.keys() and 'value' not in value.keys())
            ):
                raise HoustonException(
                    log,
                    'value must contain keys "guid" and at least one of: "context", "value"',
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                )
            name = Name.query.get(value['guid'])
            if not name or name.individual_guid != obj.guid:
                raise HoustonException(
                    log,
                    f"invalid name guid {value['guid']}",
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                )
            if 'context' in value:
                name.context = value['context']
            if 'value' in value:
                name.value = value['value']
            ret_val = True

        return ret_val
