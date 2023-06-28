# -*- coding: utf-8 -*-
"""
Input arguments (Parameters) for Individuals resources RESTful API
-----------------------------------------------------------
"""
import logging
from uuid import UUID

from flask_marshmallow import base_fields

import app.modules.utils as util
from app.utils import HoustonException
from flask_restx_patched import Parameters, PatchJSONParameters

from . import schemas

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class CreateIndividualParameters(Parameters, schemas.CreateIndividualSchema):
    names = base_fields.List(
        base_fields.Raw(),
        description='List of Individual Names',
        required=False,
    )
    encounters = base_fields.List(
        base_fields.Raw(),
        description='List of Encounter ids',
        required=False,
    )

    class Meta(schemas.CreateIndividualSchema.Meta):
        pass


class PatchIndividualDetailsParameters(PatchJSONParameters):
    # pylint: disable=abstract-method,missing-docstring
    OPERATION_CHOICES = (
        PatchJSONParameters.OP_REPLACE,
        PatchJSONParameters.OP_ADD,
        PatchJSONParameters.OP_REMOVE,
    )

    PATH_CHOICES = (
        '/featuredAssetGuid',
        '/names',
        '/encounters',
        '/sex',
        '/taxonomy',
        '/timeOfBirth',
        '/timeOfDeath',
        '/comments',
        '/customFields',
    )

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
        elif field == 'featuredAssetGuid':
            # It is permitted to get rid of this without replacing it as without it, the code will 'guess' one
            obj.featured_asset_guid = None
            ret_val = True
        elif field == 'sex':
            obj.sex = None
            ret_val = True
        # cdx-7 says we cannot be without taxonomy
        # elif field == 'taxonomy':
        elif field == 'timeOfBirth':
            obj.time_of_birth = None
            ret_val = True
        elif field == 'timeOfDeath':
            obj.time_of_death = None
            ret_val = True
        elif field == 'comments':
            obj.comments = None
            ret_val = True
        elif field == 'customFields':
            # in this case, `value` is actually the CustomFieldDefinition guid to remove
            #   this will raise ValueError if it is not valid
            obj.reset_custom_field_value(value)
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
                    obj=obj,
                )
            try:
                obj.remove_name(name)
            except ValueError as ve:
                raise HoustonException(
                    log,
                    f'{name} could not be removed from {obj}: {str(ve)}',
                    obj=obj,
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
            from flask_login import current_user

            from app.modules.names.models import Name
            from app.modules.users.models import User

            name = Name.query.get(value['guid'])
            if not name or name.individual_guid != obj.guid:
                raise HoustonException(
                    log, message=f"invalid name guid {value['guid']}", obj=obj
                )
            user = User.query.get(value['preferring_user'])
            # decree from 2021-12-08 slack discussion is user can only add/remove self
            #   but this can be rolled back by dropping second part of this conditional
            if not user or user != current_user:
                raise HoustonException(
                    log,
                    f"invalid user guid {value['preferring_user']}",
                    obj=obj,
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
                    obj=obj,
                )
            from flask_login import current_user

            from app.modules.autogenerated_names.models import AUTOGEN_NAME_CONTEXT_PREFIX
            from app.modules.names.models import Name
            from app.modules.users.models import User

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
                                obj=obj,
                            )
                        preferring_users.append(user)
                if value['context'].startswith(AUTOGEN_NAME_CONTEXT_PREFIX):
                    raise HoustonException(
                        log,
                        f'Cannot create name with context that begins with {AUTOGEN_NAME_CONTEXT_PREFIX}',
                        obj=obj,
                    )
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
                        obj=obj,
                    )
                user = User.query.get(value['preferring_user'])
                # see above decree from 2021-12-08
                if not user or user != current_user:
                    raise HoustonException(
                        log,
                        f"invalid user guid {value['preferring_user']}",
                        obj=obj,
                    )
                name.add_preferring_user(user)
                return True

        return cls.replace(obj, field, value, state)

    @classmethod
    def replace(cls, obj, field, value, state):
        import app.modules.utils as util

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
        elif field == 'sex':
            if not util.is_valid_sex(value):
                raise HoustonException(
                    log,
                    f'"{value}" is not a valid value for sex',
                    obj=obj,
                )
            obj.sex = value
            ret_val = True
        elif field == 'taxonomy':
            from app.modules.site_settings.models import Taxonomy

            try:
                Taxonomy(value)
            except ValueError as ve:
                raise HoustonException(
                    log,
                    f'{value} invalid taxonomy for {obj}: {str(ve)}',
                    obj=obj,
                )
            obj.taxonomy_guid = value
            ret_val = True
        elif field == 'timeOfBirth':
            if not util.is_valid_datetime_string(value):
                raise HoustonException(
                    log,
                    f'"{value}" is not a valid value for timeOfBirth',
                    obj=obj,
                )
            obj.time_of_birth = value
            ret_val = True
        elif field == 'timeOfDeath':
            if not util.is_valid_datetime_string(value):
                raise HoustonException(
                    log,
                    f'"{value}" is not a valid value for timeOfDeath',
                    obj=obj,
                )
            obj.time_of_death = value
            ret_val = True
        elif field == 'comments':
            obj.comments = value
            ret_val = True
        elif field == 'customFields':
            # see explanation on encounter patch
            assert isinstance(value, dict), 'customFields must be passed a json object'
            if value.get('id'):
                assert 'value' in value, 'customFields id/value format needs both'
                value = {value['id']: value['value']}
            obj.set_custom_field_values_json(value)  # does all the validation etc
            ret_val = True
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
                    obj=obj,
                )
            name = Name.query.get(value['guid'])
            if not name or name.individual_guid != obj.guid:
                raise HoustonException(
                    log,
                    f"invalid name guid {value['guid']}",
                    obj=obj,
                )
            if 'context' in value:
                name.context = value['context']
            if 'value' in value:
                name.value = value['value']
            ret_val = True

        return ret_val
