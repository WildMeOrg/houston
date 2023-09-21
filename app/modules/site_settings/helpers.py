# -*- coding: utf-8 -*-
"""
Site Settings interactions with other modules
This is where the knowledge is of the component specific functionality where some site settings needs to be
read/stored/validated
--------------------
"""
import datetime
import logging
import uuid

from flask_login import current_user  # NOQA

import app.extensions.logging as AuditLog  # NOQA
from app.modules import is_module_enabled
from app.utils import HoustonException

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


# Helper for validating the required fields in any level dictionary
def validate_fields(dictionary, fields, error_str):
    for field, field_type, mandatory in fields:
        if mandatory:
            if field not in dictionary:
                raise HoustonException(log, f'{field} field missing from {error_str}')
            if not isinstance(dictionary[field], field_type):
                raise HoustonException(
                    log,
                    f'{field} field had incorrect type, expected {field_type.__name__} in {error_str}',
                )

            if field_type == list:
                # All mandatory lists must have at least one entry
                if len(dictionary[field]) < 1:
                    raise HoustonException(
                        log, f'{field} in {error_str} must have at least one entry'
                    )
        elif field in dictionary:
            if not isinstance(dictionary[field], field_type):
                raise HoustonException(log, f'{field} incorrect type in {error_str}')

        if (
            mandatory
            and field_type == str
            and field in dictionary
            and len(dictionary[field]) == 0
        ):
            raise HoustonException(log, f'{field} cannot be empty string in {error_str}')


class SiteSettingSpecies(object):
    @classmethod
    def validate(cls, value):
        from app.modules.autogenerated_names.models import (
            AutogeneratedName,
            AutogeneratedNameType,
        )

        from .models import SiteSetting

        assert isinstance(value, list)
        # we have to start with *all* autogen names (not just auto_species) for sake of validation
        new_autogen_names = SiteSetting.get_value('autogenerated_names') or {}

        species_fields = [
            ('commonNames', list, True),
            ('scientificName', str, True),
            ('itisTsn', int, False),
        ]
        for spec in value:
            validate_fields(spec, species_fields, 'site.species')
            if 'autogeneratedName' in spec and isinstance(
                spec['autogeneratedName'], dict
            ):
                agn_guid = spec['autogeneratedName'].get('guid', str(uuid.uuid4()))
                # note: 'enabled' is required to be passed here
                spec['autogeneratedName'][
                    'type'
                ] = AutogeneratedNameType.auto_species.value  # force it
                # reference_guid will get set properly in set() below; this is just to pass validation
                spec['autogeneratedName']['reference_guid'] = f'FAKEREF-{agn_guid}'
                new_autogen_names[agn_guid] = spec['autogeneratedName']

        # will throw exception if bad
        AutogeneratedName.validate_names(new_autogen_names, skip_taxonomy_check=True)

    # Needs to be a separate function to generate the id for the species
    @classmethod
    def set(cls, key, value):
        from app.modules.autogenerated_names.models import (
            AutogeneratedName,
            AutogeneratedNameType,
        )

        from .models import SiteSetting

        # we have to start with *all* autogen names (not just auto_species) for sake of setting
        new_autogen_names = SiteSetting.get_value('autogenerated_names') or {}

        # current behavior is as follows: since this sets *all taxonomy*, we trust it to also set *all taxonomy AGN
        #   as such, it will disable any (existing) taxonomy AGN not represented here (e.g. taxonomy removed or no AGN given!)
        tx_agn = []
        for spec in value:
            if 'id' not in spec:
                spec['id'] = str(uuid.uuid4())
            if 'autogeneratedName' in spec and isinstance(
                spec['autogeneratedName'], dict
            ):
                agn_guid = spec['autogeneratedName'].pop('guid', str(uuid.uuid4()))
                tx_agn.append(agn_guid)
                new_autogen_names[agn_guid] = spec['autogeneratedName']
                del spec['autogeneratedName']
                # now we set some forced/required values here:
                new_autogen_names[agn_guid][
                    'type'
                ] = AutogeneratedNameType.auto_species.value
                new_autogen_names[agn_guid]['reference_guid'] = spec['id']

        log.debug(
            f'updating Houston Setting key={key} value={value} new_autogen_names={new_autogen_names}'
        )
        SiteSetting.set_after_validation(key, value)

        # here is where we disable possible previous taxonomy AGNs that are now unused
        for agn_guid in new_autogen_names:
            if (
                new_autogen_names[agn_guid]['type']
                == AutogeneratedNameType.auto_species.value
                and agn_guid not in tx_agn
                and new_autogen_names[agn_guid]['enabled']
            ):
                log.debug(
                    f'disabling {agn_guid}:{new_autogen_names[agn_guid]} due to not set via site.species'
                )
                new_autogen_names[agn_guid]['enabled'] = False
        if new_autogen_names:
            AutogeneratedName.set_names_as_rest(new_autogen_names)
            SiteSetting.set_after_validation(
                'autogenerated_names', new_autogen_names
            )  # this SiteSetting also needs updating


class SiteSettingModules(object):
    @classmethod
    def validate_autogen_names(cls, value):
        if is_module_enabled('autogenerated_names'):
            from app.modules.autogenerated_names.models import AutogeneratedName

            return AutogeneratedName.validate_names(value)
        else:
            return []

    @classmethod
    def update_autogen_names(cls, value):
        if is_module_enabled('autogenerated_names'):
            from app.modules.autogenerated_names.models import AutogeneratedName

            AutogeneratedName.set_names_as_rest(value)

    @classmethod
    def validate_social_group_roles(cls, value):
        if is_module_enabled('social_groups'):
            from app.modules.social_groups.models import SocialGroup

            SocialGroup.validate_roles(value)

    @classmethod
    def update_social_group_roles(cls, value=None):
        if is_module_enabled('social_groups'):
            from app.modules.social_groups.models import SocialGroup

            SocialGroup.site_settings_updated()

    @classmethod
    def validate_relationship_type_roles(cls, value):
        from .schemas import RelationshipTypeSchema

        if not isinstance(value, dict):
            raise HoustonException(log, 'value must be a dict')
        schema = RelationshipTypeSchema()
        for relationship_object in value.values():
            errors = schema.validate(relationship_object)
            if errors:
                raise HoustonException(log, schema.get_error_message(errors))


class SiteSettingCustomFields(object):
    # source: Custom Fields in Wildbook EDM [sic] google doc
    DISPLAY_TYPES = {
        'string': str,
        'longstring': str,
        'select': str,
        'multiselect': list,
        'boolean': bool,
        'integer': int,
        'float': float,
        'date': datetime.datetime,
        'daterange': list,  # [ datetime, datetime ]
        'feetmeters': float,  # assumed stored as meters
        'latlong': list,  # [ decimalLatitude, decimalLongitude ]
        'individual': uuid.UUID,
        # 2022-08-12 meeting established these as "maybe" so any support here is minimal/tentative
        'specifiedTime': dict,  # { time: datetime, timeSpecificity: string (ComplexDateTime.specificities) }
        'locationId': uuid.UUID,
        'file': uuid.UUID,  # FileUpload guid, DEX-1261
        # 'relationship': guid,   # DEX-1155  (not even minimal support)
    }

    @classmethod
    def validate_categories(cls, value):
        from .models import SiteSetting

        if not isinstance(value, list):
            raise HoustonException(log, 'customFieldCategories needs to be a list')
        # there is potential race conditions here, but ... well ... yknow
        prev_list = SiteSetting.get_value('site.custom.customFieldCategories') or []
        prev_cat = {}
        for cat in prev_list:
            prev_cat[cat['id']] = cat

        by_cat = cls.definitions_by_category()  # cat_guid => [defns]
        category_fields = [
            ('id', str, True),
            ('label', str, True),
            ('type', str, True),
        ]
        # starts with all, but we .remove() as they are defined
        deleted_guids = list(prev_cat.keys())
        for cat in value:
            validate_fields(cat, category_fields, 'customFieldCategories')
            if cat['type'] not in ['encounter', 'sighting', 'individual']:
                raise HoustonException(
                    log, f'customFieldCategories item {cat} includes invalid type'
                )
            # we only allow type-change (enc/sight/indiv) if unused by any definitions
            if (
                cat['id'] in prev_cat
                and prev_cat[cat['id']]['type'] != cat['type']
                and cat['id'] in by_cat
            ):
                raise HoustonException(
                    log,
                    f'customFieldCategories item {cat} cannot modify an existing category type',
                )
            if cat['id'] in deleted_guids:
                deleted_guids.remove(cat['id'])

        # we dont care if the customField definition actually has data or not as we dont cascade
        #   leave that to removing the definition *first*, then this will be allowed
        if deleted_guids:
            for guid in deleted_guids:
                if guid in by_cat:
                    raise HoustonException(
                        log,
                        f'customFieldCategories guid {guid} was removed but is still in use by {len(by_cat[guid])} customField definition(s)',
                    )

    # returns all (by default) or just one
    @classmethod
    def definitions_by_category(cls, single=None):
        from .models import SiteSetting

        all_cats = ['Encounter', 'Sighting', 'Individual']
        if single and single not in all_cats:
            raise ValueError(f'{single} not in {all_cats}')
        if single:
            all_cats = [single]
        by_cat = {}
        for class_name in all_cats:
            data = SiteSetting.get_value(f'site.custom.customFields.{class_name}') or {}
            definitions = data.get('definitions', [])
            for defn in definitions:
                if defn['schema']['category'] not in by_cat:
                    by_cat[defn['schema']['category']] = []
                by_cat[defn['schema']['category']].append(defn)
        return by_cat

    # class_name is Captitalized (Encounter, Sighting, Individual)
    @classmethod
    def _validate_fields(cls, value, class_name):
        from .models import SiteSetting

        field_str = f'customFields.{class_name}'
        if 'definitions' not in value:
            raise HoustonException(log, f"{field_str} must contain a 'definitions' block")
        defs = value['definitions']
        if not isinstance(defs, list):
            raise HoustonException(log, f'{field_str} needs to be a list')
        custom_fields = [
            ('id', str, True),
            ('name', str, True),
            ('schema', dict, True),
            ('multiple', bool, True),
        ]
        schema_fields = [
            ('category', str, True),
            ('description', str, False),
            ('displayType', str, True),
            ('label', str, True),
        ]
        categories = SiteSetting.get_value('site.custom.customFieldCategories')
        current_data = SiteSetting.get_value(f'site.custom.{field_str}')
        existing_ids = []
        existing_fields = []
        if current_data:
            existing_fields = current_data.get('definitions')
            existing_ids = [exist['id'] for exist in existing_fields]
        dropped_ids = existing_ids.copy()  # will be whittled down

        # 'type' value is all lowercase, thus:
        category_ids = [
            cat['id'] for cat in categories if cat['type'] == class_name.lower()
        ]
        for cf_def in defs:
            validate_fields(cf_def, custom_fields, field_str)
            validate_fields(cf_def['schema'], schema_fields, f'{field_str} schema')
            cf_cat_id = cf_def['schema']['category']
            if cf_cat_id not in category_ids:
                raise HoustonException(
                    log, f'{field_str} category-id {cf_cat_id} not found'
                )
            cf_id = cf_def['id']
            if cf_id in dropped_ids:
                dropped_ids.remove(cf_id)
            if cf_id in existing_ids:
                current_val = [
                    current for current in existing_fields if current['id'] == cf_id
                ]
                assert len(current_val) == 1
                if current_val[0] != cf_def:
                    # this will raise exception if trouble
                    cls._change_data(current_val[0], cf_def, class_name)
            display_type = cf_def['schema']['displayType']
            if display_type not in cls.DISPLAY_TYPES:
                raise HoustonException(
                    log,
                    f'{field_str} id {cf_cat_id}: displayType {display_type} not valid',
                )

            if display_type == 'multiselect' and not cf_def.get('multiple', False):
                raise HoustonException(
                    log,
                    f'{field_str} id {cf_cat_id}: multiselect must have multiple=true',
                )

            # see DEX-1270
            try:
                # this will silently be ignored if not multi/select but ValueError if badness
                cls.get_choices_from_definition(cf_def, value_only=True)
            except ValueError as verr:
                raise HoustonException(log, f'{field_str} id {cf_cat_id}: {str(verr)}')

        # after iterating thru defs, if we have anything in dropped_ids, it means it is a definition we _had_ but
        #   has not been sent, so must have been dropped.  now we deal with that.
        for cf_id in dropped_ids:
            cls._drop_data(cf_id, class_name)

    @classmethod
    def get_definition(cls, cls_name, guid):
        from .models import SiteSetting

        # bad cls_name will get raise HoustonException
        data = SiteSetting.get_value(f'site.custom.customFields.{cls_name}')
        if not data or not isinstance(data.get('definitions'), list):
            return None
        for defn in data['definitions']:
            if guid == defn.get('id'):
                return defn
        return None

    @classmethod
    def get_definitions(cls, cls_name):
        from .models import SiteSetting

        # bad cls_name will get raise HoustonException
        data = SiteSetting.get_value(f'site.custom.customFields.{cls_name}')
        if not data or not isinstance(data.get('definitions'), list):
            return []
        return data['definitions']

    # WARNING: this does no safety check (_drop_data etc), so really other code that
    #   wraps this should be used, e.g. patch_remove()
    @classmethod
    def remove_definition(cls, class_name, guid):
        from .models import SiteSetting

        # bad class_name will get raise HoustonException
        data = SiteSetting.get_value(f'site.custom.customFields.{class_name}')
        if not data or not isinstance(data.get('definitions'), list):
            return
        new_list = []
        found = False
        for defn in data['definitions']:
            if guid == defn.get('id'):
                found = True
            else:
                new_list.append(defn)
        if found:
            AuditLog.audit_log(log, f'remove_definition dropped {guid} for {class_name}')
            SiteSetting.set_rest_block_data(
                {f'site.custom.customFields.{class_name}': {'definitions': new_list}}
            )

    @classmethod
    # tries to always return at least _something_
    def nice_name(cls, class_name, guid):
        defn = cls.get_definition(class_name, guid) or {'id': guid}
        if 'schema' in defn and defn['schema'].get('label'):
            return defn['schema']['label']
        return defn.get('name') or defn.get('id', 'UNKNOWN')

    # expects cf_defn as from above
    # NOTE this is very very likely incomplete.  the 'type' value in definitions are quite complex.
    #    probably need to check in with FE for what is actually needed
    #    see also:  valid_display_types under _validate_fields
    #
    # !! a NOTE on None ... it remains to be seen if None *always should* be allowed as a valid value,
    #    regardless of type/scenario.  for now, it is allowed (except where choices is involved)
    #    a None will cause the customField to have an entry like { CFD_ID: None } ... which is -- what it is.
    #    the more pedantic among us might prefer to use op=remove for this scenario, i suppose
    @classmethod
    def is_valid_value(cls, cf_defn, value):
        import copy

        import app.modules.utils as util

        dtype = cf_defn['schema']['displayType']

        try:
            choices = cls.get_choices_from_definition(cf_defn, value_only=True)
        except ValueError as verr:
            # this means we need choices (multi/select) but badness happened
            log.debug(f'needed choices for {cf_defn} but failed due to: {str(verr)}')
            return False

        # because daterange sets multiple=T we need to do this multi-value checking *before* we recurse for multiple... i guess?
        #  BUT we only test this when we are passed a *list value* (cuz otherwise we have recursed! wtf)
        if dtype == 'daterange' and isinstance(value, list):
            if len(value) != 2:
                log.debug(f'daterange must be a list of length 2: {value}')
                return False
            if value[0] is None and value[1] is None:
                return True  # ok(ish)
            if not isinstance(value[0], datetime.datetime):
                log.debug(f'daterange value0={value[0]} must a datetime')
                return False
            if not isinstance(value[1], datetime.datetime):
                log.debug(f'daterange value1={value[1]} must a datetime')
                return False
            delta = value[1] - value[0]
            if delta.total_seconds() < 0:
                log.debug(
                    f'daterange {value[0]} > {value[1]} older datetime must come first'
                )
                return False

        if cf_defn.get('multiple', False):
            if value is None and not cf_defn.get('required', False):
                return True  # seems legit?
            if not isinstance(value, list):
                log.debug(f'multiple=T but value not list: value={value} defn={cf_defn}')
                return False
            if len(value) == 0 and cf_defn.get('required', False):
                log.debug(
                    f'multiple=T and required=T but empty list: value={value} defn={cf_defn}'
                )
                return False
            # a little hackery / slight-of-hand
            cf_defn_single = copy.deepcopy(cf_defn)
            cf_defn_single['multiple'] = False
            if dtype == 'multiselect':  # bonus hackery
                cf_defn_single['schema']['displayType'] = 'select'
            if dtype == 'daterange':  # bonus bonus hackery
                cf_defn_single['schema']['displayType'] = 'date'
            for val in value:
                val_ok = cls.is_valid_value(cf_defn_single, val)
                if not val_ok:
                    return False
            return True  # all passed

        # since we arent multiple, we let None be acceptable except:
        #   1. we are required  -and-
        #   2. we have choices (that dont include None)
        if value is None:
            # special case when required + None is allowed (via choices)
            if cf_defn.get('required', False) and choices and None in choices:
                return True
            if cf_defn.get('required', False):
                log.debug('required=True, but value=None (and None not in choices)')
                return False
            return True

        # defaults to str if unknown displayType
        instance_type = cls.DISPLAY_TYPES.get(dtype, str)

        # hack to allow ints to pass where floats wanted
        if instance_type == float and isinstance(value, int):
            instance_type = int

        # want int, got string, try conversion
        if instance_type == int and isinstance(value, str):
            try:
                value = int(value)
            except Exception as ex:
                log.debug(
                    f'value string "{value}" could not be made into an int: {str(ex)}'
                )
                return False

        # want float, got string, try conversion
        if instance_type == float and isinstance(value, str):
            try:
                value = float(value)
            except Exception as ex:
                log.debug(
                    f'value string "{value}" could not be made into an float: {str(ex)}'
                )
                return False

        # try to convert str to uuid if appropriate
        if instance_type == uuid.UUID and isinstance(value, str):
            try:
                value = uuid.UUID(value, version=4)
            except Exception as ex:
                log.debug(
                    f'value string "{value}" could not be made into a UUID: {str(ex)}'
                )
                return False

        if not isinstance(value, instance_type):
            log.debug(
                f'value not instance of {str(instance_type)}: value={value} defn={cf_defn}'
            )
            return False

        # must have choices
        if dtype == 'select' and value not in choices:
            log.debug(f'value {value} not in choices {choices}')
            return False

        # must have choices
        if dtype == 'multiselect':
            if not value and cf_defn.get('required', False):
                log.debug('required=True, but value=[]')
                return False
            for mval in value:
                if mval not in choices:
                    log.debug(f'value {mval} not in choices {choices}')
                    return False

        if dtype == 'locationId':
            from app.modules.site_settings.models import Regions

            if not Regions.is_region_guid_valid(value):
                log.debug(f'invalid Region guid {value}')
                return False

        if dtype == 'individual':
            from app.modules.individuals.models import Individual

            # TODO should there be an ownership/stakeholder/permission restriction here?
            if not Individual.query.get(value):
                log.debug(f'invalid Individual guid {value}')
                return False

        if dtype == 'file':
            from app.modules.fileuploads.models import FileUpload

            # TODO should there be an ownership/permission restriction here?
            if not FileUpload.query.get(value):
                log.debug(f'invalid FileUpload guid {value}')
                return False

        if dtype == 'specifiedTime':
            from app.modules.complex_date_time.models import ComplexDateTime

            try:
                ComplexDateTime.from_data(value)
            except ValueError:
                # from_data() logs plenty, so none here
                return False

        # for whatever reason, latlong is multiple=F (whereas daterange is multiple=T) so this needs to be done here
        if dtype == 'latlong':
            if len(value) != 2:
                log.debug(f'latlong value={value} must contain exactly 2 items')
                return False
            if isinstance(value[0], int):
                value[0] = float(value[0])
            if isinstance(value[1], int):
                value[1] = float(value[1])
            if value[0] is None and value[1] is None:
                if cf_defn.get('required', False):
                    log.debug('latlong is mandatory')
                    return False
            elif not util.is_valid_latitude(value[0]):
                log.debug(f'latlong latitude={value[0]} is invalid')
                return False
            elif not util.is_valid_longitude(value[1]):
                log.debug(f'latlong longitude={value[1]} is invalid')
                return False

        # we made it!!
        return True

    @classmethod
    def is_valid_value_for_class(cls, cls_name, cfd_id, value):
        defn = cls.get_definition(cls_name, cfd_id)
        if not defn:
            return False
        if not cls.is_valid_value(defn, value):
            return False
        return True

    # turn it into how we want it stored in json for db
    #   note we assume everything is in order here - no validating!
    @classmethod
    def serialize_value(cls, class_name, cfd_id, value):
        defn = cls.get_definition(class_name, cfd_id)
        assert defn
        return cls._serialize_value_using_definition(defn, value)

    @classmethod
    def _serialize_value_using_definition(cls, defn, value):
        if value is None:
            return None

        if defn.get('multiple', False):
            import copy

            if not isinstance(value, list):
                log.error(f'multiple=T but value not list: value={value} defn={defn}')
                raise ValueError('multiple=T but value is not list')
            # recursive hackery
            defn_single = copy.deepcopy(defn)
            defn_single['multiple'] = False
            arr = []
            for val in value:
                arr.append(cls._serialize_value_using_definition(defn_single, val))
            return arr

        dtype = defn['schema']['displayType']
        # daterange *should* have multiple=T so it will have recursed to single values here
        if dtype == 'date' or dtype == 'daterange':
            return value.isoformat()
        # if dtype == 'daterange':
        # return [value[0].isoformat(), value[1].isoformat()]
        if cls.DISPLAY_TYPES[dtype] == uuid.UUID:
            return str(value)
        return value

    # opposite of above
    @classmethod
    def deserialize_value(cls, defn, raw_value):
        if raw_value is None:
            return None

        if defn.get('multiple', False):
            import copy

            if not isinstance(raw_value, list):
                log.error(f'multiple=T but value not list: value={raw_value} defn={defn}')
                raise ValueError('multiple=T but value is not list')
            # recursive hackery
            defn_single = copy.deepcopy(defn)
            defn_single['multiple'] = False
            arr = []
            for val in raw_value:
                arr.append(cls.deserialize_value(defn_single, val))
            return arr

        dtype = defn['schema']['displayType']
        # daterange *should* have multiple=T so it will have recursed to single values here
        if (dtype == 'date' or dtype == 'daterange') and not isinstance(
            raw_value, datetime.datetime
        ):
            return datetime.datetime.fromisoformat(raw_value)
        if cls.DISPLAY_TYPES[dtype] == uuid.UUID and isinstance(raw_value, str):
            return uuid.UUID(raw_value, version=4)
        return raw_value

    # will raise ValueError if should be one but something is wonky
    #    will silently return None if there just should not be any
    # will return array of choice objects (or just value-strings if value_only=True)
    @classmethod
    def get_choices_from_definition(cls, defn, value_only=False):
        if not isinstance(defn, dict):
            raise ValueError('definition must be dict')
        if not isinstance(defn.get('schema'), dict):
            raise ValueError('definition must have a schema')
        if defn['schema'].get('displayType') not in ['select', 'multiselect']:
            return None
        if not isinstance(defn['schema'].get('choices'), list):
            raise ValueError('choices is required and must be a list')
        # i guess we allow only 1 choice?
        if len(defn['schema']['choices']) < 1:
            raise ValueError('choices must have at least one value')
        choices = []
        values = []
        for choice in defn['schema']['choices']:
            if not isinstance(choice, dict):
                raise ValueError(f'choices item {choice} is not a dict')
            if 'label' not in choice:
                raise ValueError(f'choices item {choice} missing label')
            if 'value' not in choice:
                raise ValueError(f'choices item {choice} missing value')
            value = choice['value']
            if value in values:
                raise ValueError(f'choices item {choice} has duplicate value')
            choices.append(choice)
            values.append(value)
        if value_only:
            return values
        return choices

    # DEX-1337 PATCH op=remove path=site.custom.customFields.CLASS/GUID must be supported
    #   this also will be called for (currently unused) PATCH op=remove path=site.custom.customFieldCategories fwiw (see DEX-1362)
    #   force_removal=True means go ahead and blow away all the data that exists.  ouch!
    #
    #   note: this *intentionally* disallows straight-up reseting entire customFields.CLASS object.  youre welcome.
    @classmethod
    def patch_remove(cls, key, force_removal=False):
        import re

        match_obj = re.search(r'site.custom.customFields.(\w+)/([\w\-]+)', key)
        assert match_obj and len(match_obj.groups()) == 2
        class_name = match_obj.group(1)
        cf_id = match_obj.group(2)
        defn = cls.get_definition(class_name, cf_id)
        if not defn:
            raise ValueError(f'invalid guid {cf_id} for class {class_name}')
        # FIXME _drop_data does not yet take into consideration force=True so this needs fixing
        #       for now it will just outright fail if there is data (safest route)
        cls._drop_data(cf_id, class_name)
        cls.remove_definition(class_name, cf_id)

    # "in the future" this can be much smarter, including things like:
    # - checking valid transformations, like int -> float etc.
    # - looking at modifications of schema.choices and check for validity
    # - possibly providing hints at transforming (e.g. "Male" becomes "male")
    #
    # for now, it basically will disallow changing a definition *if it is used at all*
    @classmethod
    def _change_data(cls, cf_def_old, cf_def_new, class_name):
        cf_id = cf_def_new.get('id')
        assert cf_id
        objs_using = cls._find_data(cf_id, class_name)
        if objs_using:
            raise HoustonException(
                log,
                f'customFields.{class_name} id {cf_id} in use by {len(objs_using)} objects; cannot be changed',
            )

    # like above, for now we just fail to let a CustomFieldDefinition be dropped *if it is used at all*
    #   (but can expand later to check for data, admin verification of data-loss, etc)
    #  TODO this should also be used when PATCH op=remove of a CFD:   (note 'force' boolean to destroy data)
    #      {'force': False, 'op': 'remove', 'path': 'site.custom.customFields.Encounter/DEFNGUID'}
    #      DEX 1337 will sort this out
    @classmethod
    def _drop_data(cls, cf_id, class_name):
        assert cf_id
        objs_using = cls._find_data(cf_id, class_name)
        if objs_using:
            raise HoustonException(
                log,
                f'customFields.{class_name} id {cf_id} in use by {len(objs_using)} objects; cannot be dropped',
            )

    # NOTE a bit hactacular/experimental
    #   this is for finding actual objects which are using (have values for) a given customFieldDefinition
    @classmethod
    def _find_data(cls, cf_id, class_name):
        # hacky - it limits us to these 3 classes, alas
        from app.extensions import db
        from app.modules.encounters.models import Encounter
        from app.modules.individuals.models import Individual
        from app.modules.sightings.models import Sighting

        assert cf_id
        cls_map = {
            'Encounter': Encounter,
            'Sighting': Sighting,
            'Individual': Individual,
        }
        cls = cls_map.get(class_name)
        assert cls
        has_values = []
        res = db.session.execute(
            # h/t https://stackoverflow.com/a/68679549 for this madness
            f'SELECT guid FROM {class_name.lower()} WHERE (custom_fields #>> \'{{}}\')::jsonb->\'{cf_id}\' IS NOT NULL'
        )
        for row in res:
            obj = cls.query.get(row[0])
            has_values.append(obj)
        return has_values

    @classmethod
    def validate_encounters(cls, value):
        cls._validate_fields(value, 'Encounter')

    @classmethod
    def validate_sightings(cls, value):
        cls._validate_fields(value, 'Sighting')

    @classmethod
    def validate_individuals(cls, value):
        cls._validate_fields(value, 'Individual')
