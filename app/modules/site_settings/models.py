# -*- coding: utf-8 -*-
"""
Site Settings database models
--------------------
"""
import logging
import uuid

from flask import current_app
from flask_login import current_user  # NOQA

from app.extensions import Timestamp, db, is_extension_enabled
from app.utils import HoustonException

from .helpers import SiteSettingCustomFields, SiteSettingModules, SiteSettingSpecies

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class SiteSetting(db.Model, Timestamp):
    """
    Site Settings database model.
    """

    __mapper_args__ = {
        'confirm_deleted_rows': False,
    }

    # public=False means the setting is only used in the backend
    HOUSTON_SETTINGS = {
        'site.name': {
            'type': str,
            'definition': {'schema': {'panel': True}},
            'default': '<your site name>',
        },
        'site.private': {
            'type': bool,
            'definition': {
                'schema': {'panel': True},
                'displayType': 'boolean',
                'fieldType': 'boolean',
            },
            'default': True,
        },
        'site.needsSetup': {
            'type': bool,
            'definition': {
                'schema': {'hidden': True},
                'displayType': 'boolean',
                'fieldType': 'boolean',
            },
            'default': True,
        },
        'site.species': {
            'type': list,
            'definition': {
                'displayType': 'taxonomy',
            },
            'validate_function': SiteSettingSpecies.validate,
            'set_function': SiteSettingSpecies.set,
        },
        'site.general.description': {
            'type': str,
            'default': 'Researchers use <your site name> to identify and organize sightings of <your species here>.',
            'definition': {
                'displayType': 'longstring',
                'fieldType': 'string',
            },
        },
        'site.general.tagline': {
            'type': str,
            'definition': {
                'displayType': 'string',
                'fieldType': 'string',
            },
            'default': 'Welcome to <your site name>',
        },
        'site.general.taglineSubtitle': {
            'type': str,
            'definition': {
                'displayType': 'longstring',
                'fieldType': 'string',
            },
            'default': 'AI for the conservation of <your species here>.',
        },
        'site.general.donationButtonUrl': {
            'type': str,
            'definition': {
                'displayType': 'string',
                'fieldType': 'url',
            },
        },
        'site.general.helpDescription': {
            'type': str,
            'definition': {
                'displayType': 'longstring',
                'fieldType': 'string',
            },
            'default': 'Every sighting counts! Citizen scientist reports make a big difference. We also accept donations to support the continued development of <your site name>.',
        },
        'site.general.customCardButtonText': {
            'type': str,
            'definition': {
                'displayType': 'longstring',
                'fieldType': 'string',
            },
            'default': 'Take action',
        },
        'site.general.customCardButtonUrl': {
            'type': str,
            'definition': {
                'displayType': 'string',
                'fieldType': 'url',
            },
            'default': 'Take action',
        },
        'site.general.customCardLine1': {
            'type': str,
            'definition': {
                'displayType': 'longstring',
                'fieldType': 'string',
            },
            'default': 'Set up your custom card in the site configuration menu.',
        },
        'site.general.customCardLine2': {
            'type': str,
            'definition': {
                'displayType': 'longstring',
                'fieldType': 'string',
            },
            'default': 'Set up your custom card in the site configuration menu.',
        },
        'site.general.photoGuidelinesUrl': {
            'type': str,
            'definition': {
                'displayType': 'string',
                'fieldType': 'url',
            },
        },
        'site.look.themeColor': {
            'type': str,
            'definition': {
                'schema': {},
                'displayType': 'color',
            },
            'default': '#68F6E5',
        },
        'site.look.logoIncludesSiteName': {
            'type': bool,
            'definition': {
                'displayType': 'boolean',
            },
            'default': False,
        },
        'site.links.facebookLink': {
            'type': str,
            'definition': {
                'fieldType': 'url',
            },
        },
        'site.links.instagramLink': {
            'type': str,
            'definition': {
                'fieldType': 'url',
            },
        },
        'site.links.twitterLink': {
            'type': str,
            'definition': {
                'fieldType': 'url',
            },
        },
        'site.custom.regions': {
            'type': dict,
            'definition': {
                'displayType': 'locationIds',
            },
            'validate_function': SiteSettingModules.validate_regions,
        },
        'site.custom.customFieldCategories': {
            'type': list,
            'definition': {
                'displayType': 'categoryList',
            },
            'default': [],
            'validate_function': SiteSettingCustomFields.validate_categories,
        },
        'site.custom.customFields.Encounter': {
            'type': dict,
            'definition': {
                'displayType': 'customFields',
            },
            'validate_function': SiteSettingCustomFields.validate_encounters,
        },
        'site.custom.customFields.Sighting': {
            'type': dict,
            'definition': {
                'displayType': 'customFields',
            },
            'validate_function': SiteSettingCustomFields.validate_sightings,
        },
        'site.custom.customFields.Individual': {
            'type': dict,
            'definition': {
                'displayType': 'customFields',
            },
            'validate_function': SiteSettingCustomFields.validate_individuals,
        },
        'preferred_language': {
            'type': str,
            'default': 'en_us',
        },
        'email_service': {
            'type': str,
            'public': False,
            'definition': {
                'defaultValue': '',
                'displayType': 'select',
                'schema': {
                    'choices': [
                        {'label': 'Do not send mail', 'value': ''},
                        {'label': 'Mailchimp/Mandrill', 'value': 'mailchimp'},
                    ]
                },
            },
            'default': lambda: current_app.config.get('DEFAULT_EMAIL_SERVICE'),
        },
        'email_service_username': {
            'type': str,
            'public': False,
            'default': lambda: current_app.config.get('DEFAULT_EMAIL_SERVICE_USERNAME'),
        },
        'email_service_password': {
            'type': str,
            'public': False,
            'default': lambda: current_app.config.get('DEFAULT_EMAIL_SERVICE_PASSWORD'),
        },
        'email_default_sender_email': {
            'type': str,
            'public': False,
            'default': lambda: current_app.config['MAIL_DEFAULT_SENDER'][1],
        },
        'email_default_sender_name': {
            'type': str,
            'public': False,
            'default': lambda: current_app.config['MAIL_DEFAULT_SENDER'][0],
        },
        'email_header_image_url': {
            'type': str,
            'public': False,
        },
        'email_title_greeting': {
            'type': str,
            'public': False,
            'default': 'Hello!',
        },
        'email_secondary_title': {
            'type': str,
            'public': False,
            'default': 'Codex for everyone!',
        },
        'email_secondary_text': {
            'type': list,
            'public': False,
            'default': [
                'Can you help researchers study and protect animals?',
                'Wild Me is a 501(c)(3) non-profit that develops the cutting edge technology for a global community of wildlife researchers. Are you interested in further supporting our mission?',
            ],
        },
        'email_adoption_button_text': {
            'type': str,
            'public': False,
            'default': 'Adopt an animal',
        },
        'email_legal_statement': {
            'type': str,
            'public': False,
            'default': 'Wildbook is copyrighted 2022 by Wild Me.  Individual contributors to Wildbook retain copyrights for submitted images. No reproduction or usage of material in this library is permitted without the express permission of the copyright holders.',
        },
        'social_group_roles': {
            'type': list,
            'public': True,
            'validate_function': SiteSettingModules.validate_social_group_roles,
            'update_function': SiteSettingModules.update_social_group_roles,
        },
        'relationship_type_roles': {
            'type': dict,
            'public': True,
            'validate_function': SiteSettingModules.validate_relationship_type_roles,
            'definition': {
                'fieldType': 'json',
                'displayType': 'relationship-type-role',
                'required': False,
            },
        },
        'autogenerated_names': {
            'type': dict,
            'public': True,
            'validate_function': SiteSettingModules.validate_autogen_names,
            'update_function': SiteSettingModules.update_autogen_names,
            'definition': {
                'fieldType': 'json',
                'displayType': 'autogenerated-names',
                'required': False,
            },
        },
        # setting this will be disallowed to be set via api (must be done elsewhere in code by using override_readonly)
        'system_guid': {
            'type': str,
            'public': True,
            'read_only': True,
            'definition': {
                'readOnly': True,
                'settable': False,
            },
        },
        'transloaditKey': {
            'type': str,
            'public': False,
            'default': lambda: current_app.config.get('TRANSLOADIT_KEY'),
        },
        'transloaditTemplateId': {
            'type': str,
            'public': False,
            'default': lambda: current_app.config.get('TRANSLOADIT_TEMPLATE_ID'),
        },
        'transloaditService': {
            'type': str,
            'public': False,
            'default': lambda: current_app.config.get('TRANSLOADIT_SERVICE'),
        },
        'googleMapsApiKey': {
            'type': str,
            'public': True,
            'default': lambda: current_app.config.get('GOOGLE_MAPS_API_KEY'),
        },
        'sentryDsn': {
            'type': str,
            'public': True,
            'default': lambda: current_app.config.get('SENTRY_DSN'),
            # sentry is only initialized once in
            # app/extensions/sentry/__init__.py so changing the sentryDsn site
            # setting wouldn't change where the errors are sent... For now,
            # make sentryDsn read only
            'read_only': True,
            'definition': {
                'readOnly': True,
                'settable': False,
            },
        },
        'flatfileKey': {
            'type': str,
            'public': True,
            'permission': lambda: not current_user.is_anonymous,
            'default': lambda: current_app.config.get('FLATFILE_KEY'),
        },
        'recaptchaPublicKey': {
            'type': str,
            'public': True,
            'default': lambda: current_app.config.get('RECAPTCHA_PUBLIC_KEY'),
        },
        'recaptchaSecretKey': {
            'type': str,
            'public': False,
            'default': lambda: current_app.config.get('RECAPTCHA_SECRET_KEY'),
        },
        'logo': {'type': 'file', 'public': True},
        'splashImage': {'type': 'file', 'public': True},
        'splashVideo': {'type': 'file', 'public': True},
        'customCardImage': {'type': 'file', 'public': True},
        'individualMergeDefaultDelayDays': {'type': int, 'public': False, 'default': 14},
    }

    if is_extension_enabled('intelligent_agent'):
        from app.extensions.intelligent_agent.models import IntelligentAgent

        HOUSTON_SETTINGS.update(IntelligentAgent.site_setting_config_all())

    key = db.Column(db.String, primary_key=True, nullable=False)

    file_upload_guid = db.Column(
        db.GUID, db.ForeignKey('file_upload.guid', ondelete='CASCADE'), nullable=True
    )
    file_upload = db.relationship('FileUpload', cascade='delete')
    public = db.Column(db.Boolean, default=True, nullable=False)
    string = db.Column(db.String, default='', nullable=True)
    data = db.Column(db.JSON, nullable=True)
    boolean = db.Column(db.Boolean, nullable=True)

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}(key='{self.key}' "
            f"file_upload_guid='{self.file_upload_guid}' "
            f'public={self.public})>'
        )

    def is_public(self):
        return self.public

    @classmethod
    def query_search(cls, search=None, args=None):
        """
        This function is added to replicate the functionality in FeatherModel,
        which is missing because SiteSetting does not inherit from it like other
        database models.

        A query search will allow the listing functionality to work as all other
        models in Houston.

        Ref: https://github.com/WildMeOrg/houston/pull/521#discussion_r827444934
        """
        query = cls.query
        return query

    @classmethod
    def _get_keys(cls):
        return cls.HOUSTON_SETTINGS.keys()

    @classmethod
    def is_valid_setting(cls, key):
        return key in cls._get_keys()

    @classmethod
    def get_key_type(cls, key):
        return cls.HOUSTON_SETTINGS[key]['type'] if cls.is_valid_setting(key) else None

    @classmethod
    def _get_setting_conf(cls, key):
        return cls.HOUSTON_SETTINGS[key] if cls.is_valid_setting(key) else {}

    @classmethod
    def _get_default_value(cls, key):
        def_val = ''
        if key not in cls.HOUSTON_SETTINGS:
            return def_val
        default_value = cls.HOUSTON_SETTINGS[key].get('default')
        if callable(default_value):
            return default_value()
        if default_value:
            return default_value
        if cls.HOUSTON_SETTINGS[key]['type'] == dict:
            def_val = {}
        if cls.HOUSTON_SETTINGS[key]['type'] == list:
            def_val = []
        if cls.HOUSTON_SETTINGS[key]['type'] == bool:
            def_val = False
        return def_val

    @classmethod
    def upload_file(cls, key, data):
        from http import HTTPStatus
        from pathlib import Path

        from app.modules.fileuploads.models import FileUpload

        if data.get('transactionId'):
            transaction_id = data.pop('transactionId')
            if data.get('transactionPath'):
                paths = [data.pop('transactionPath')]
            else:
                paths = None

            fups = (
                FileUpload.create_fileuploads_from_tus(transaction_id, paths=paths) or []
            )

            if len(fups) != 1:
                # Delete the files in the filesystem
                # Can't use .delete() because fups are not persisted
                for fup in fups:
                    path = Path(fup.get_absolute_path())
                    if path.exists():
                        path.unlink()
                raise HoustonException(
                    log,
                    status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                    log_message=f'Transaction {transaction_id} has {len(fups)} files, need exactly 1.',
                )

            with db.session.begin(subtransactions=True):
                db.session.add(fups[0])
            file_upload_guid = fups[0].guid
        else:
            raise HoustonException(
                log,
                log_message='The File API should only be used for manipulating files via a transactionId',
            )

        return cls.set_key_value(key, file_upload_guid)

    @classmethod
    def set_after_validation(cls, key, value):
        assert key in cls.HOUSTON_SETTINGS.keys()
        key_data = cls.HOUSTON_SETTINGS[key]

        file_upload_guid = None
        string = None
        data = None
        boolean = None
        val_type = key_data['type']
        is_public = key_data.get('public', True)
        if val_type == dict or val_type == list:
            data = value
        elif val_type == bool:
            assert isinstance(value, bool)
            boolean = value
        elif val_type == str:
            assert isinstance(value, str)
            string = value
        elif val_type == 'file':
            file_upload_guid = value
        else:
            # Catch if anyone adds a new 'type' to the houston settings
            assert False, f'Site setting type {val_type} not supported'

        # useful debug for strange issues debugging but commented out as too verbose for mainline code
        # log.debug(f'About to update Houston Setting key={key}')
        # existing = cls.query.get(key)
        # if existing:
        #     log.debug(f'currently this is {existing}')

        kwargs = {
            'key': key,
            'file_upload_guid': file_upload_guid,
            'string': string,
            'data': data,
            'boolean': boolean,
            'public': is_public,
        }
        setting = cls(**kwargs)
        with db.session.begin(subtransactions=True):
            if not cls.query.get(key):
                db.session.add(setting)
            else:
                db.session.merge(setting)
        if is_public:
            log.debug(f'updating Houston Setting key={key} value={value}')
        else:
            log.debug(f'updating Houston Setting key={key}')
        return setting

    @classmethod
    def set_key_value(cls, key, value, override_readonly=False):
        assert key in cls.HOUSTON_SETTINGS.keys()
        key_data = cls.HOUSTON_SETTINGS[key]
        assert 'type' in key_data.keys()

        if 'sub_field' in key_data:
            # some fields are passed at a sub field level, for no readily apparent reason
            if key_data['sub_field'] not in value:
                raise HoustonException(
                    log, f"{key} must be passed within a {key_data['sub_field']} part"
                )
            value = value[key_data['sub_field']]

        if key_data['type'] == 'file':
            if not isinstance(value, uuid.UUID):
                msg = f'Houston Setting key={key}, value incorrect type value={value},'
                msg += 'needs to be uuid'
                raise HoustonException(log, msg)
        elif not isinstance(value, key_data['type']):
            msg = f'Houston Setting key={key}, value incorrect type value={value},'
            msg += f'needs to be {key_data["type"]}'
            raise HoustonException(log, msg)

        if 'validate_function' in key_data:
            key_data['validate_function'](value)

        if key_data.get('read_only', False) and not override_readonly:
            raise ValueError(f'read-only key {key}')
        if 'set_function' in key_data:
            key_data['set_function'](key, value)
            setting = cls.query.get(key)
        else:
            setting = cls.set_after_validation(key, value)

        if 'update_function' in key_data:
            key_data['update_function'](value)

        return setting

    @classmethod
    def forget_key_value(cls, key):
        # this covers direct removal of both customFields.CLASS definitions and customFieldCategories
        if key.startswith('site.custom.customField'):
            raise NotImplementedError('cannot forget key value for customFields')

        assert key in cls.HOUSTON_SETTINGS.keys()
        key_data = cls.HOUSTON_SETTINGS[key]

        setting = cls.query.get(key)
        if setting:
            with db.session.begin(subtransactions=True):
                db.session.delete(setting)

            if 'update_function' in key_data:
                key_data['update_function']()

    @classmethod
    def get_value(cls, key, default=None, **kwargs):
        if not key:
            raise ValueError('key must not be None')
        if not cls.is_valid_setting(key):
            raise HoustonException(log, f'Key {key} Not supported')

        setting = cls.query.get(key)
        if not setting:
            setting_default = cls._get_default_value(key)
            if default is None and setting_default is not None:
                if callable(setting_default):
                    setting_default = setting_default()
                return setting_default
            return default
        return setting.get_val()

    def get_val(self):
        if self.file_upload_guid:
            return self.file_upload_guid
        elif self.data:
            return self.data
        elif self.boolean is not None:
            return self.boolean
        return self.string

    ##########################################################################################################
    # All the functions below are for handling the REST API functions. These need detailed access to the Site
    # Settings internals but need to understand the format of the incoming and outgoing REST messages.

    @classmethod
    def set_rest_block_data(cls, data):
        # All keys must be valid
        for key in data.keys():
            if key not in cls._get_keys():
                raise HoustonException(log, f'{key} not supported')
        for key in data.keys():
            if key in cls._get_keys():
                if data[key] is not None:
                    if cls.get_key_type(key) == 'file':
                        cls.upload_file(key, data[key])
                    else:
                        cls.set_key_value(key, data[key])
                else:
                    cls.forget_key_value(key)

    # All rest value getting needs common logic so factored out into separate function
    @classmethod
    def get_rest_value(cls, key):
        init_value = cls.get_value(key)
        key_conf = cls._get_setting_conf(key)

        # Only admin can read private data
        if not key_conf.get('public', True):
            if not current_user or current_user.is_anonymous or not current_user.is_admin:
                init_value = None
        value_not_set = init_value is None
        new_value = init_value if not value_not_set else cls._get_default_value(key)
        return new_value

    @classmethod
    def _get_definition(cls, key):
        key_conf = cls._get_setting_conf(key)
        is_public = key_conf.get('public', True)
        field_type = 'string'
        display_type = 'string'
        default = ''
        # Used for generating the ID strings used by the FE
        id_key = key.upper()
        id_key = id_key.replace('.', '_')

        # Use the default from the conf only if data is public
        if is_public:
            default = key_conf.get('default', default)
            if callable(default):
                default = default()

        definition = key_conf.get('definition')
        if definition:
            display_type = definition.get('displayType', 'string')
            field_type = definition.get('fieldType', display_type)

        data = {
            'descriptionId': f'CONFIGURATION_{id_key}_DESCRIPTION',
            'labelId': f'CONFIGURATION_{id_key}_LABEL',
            'defaultValue': default,
            'required': True,
            'fieldType': field_type,
            'displayType': display_type,
        }

        # Some variables have specific values so incorporate those as required
        extra_definition = key_conf.get('definition', None)
        if extra_definition:
            data.update(extra_definition)
        return data

    @classmethod
    def get_all_rest_definitions(cls):
        from flask import url_for

        from app.modules.users.models import User

        definitions = {'site.adminUserInitialized': User.admin_user_initialized()}

        # Create the site.images
        settings = cls.query.filter_by(public=True).order_by('key')
        site_images = {}
        for setting in settings:
            if setting.file_upload is not None:
                site_images[setting.key] = url_for(
                    'api.fileuploads_file_upload_src_u_by_id_2',
                    fileupload_guid=str(setting.file_upload.guid),
                    _external=False,
                )
        definitions['site.images'] = site_images

        # Populate all the values that are accessible to the current user
        is_admin = getattr(current_user, 'is_admin', False)
        for key, type_def in cls.HOUSTON_SETTINGS.items():
            is_file = type_def.get('type') == 'file'
            permission = type_def.get('permission', lambda: True)()
            if not is_file:

                if is_admin or type_def.get('public', True) and permission:
                    definitions[key] = {
                        'value': cls.get_rest_value(key),
                        'canView': True,
                    }
                else:
                    definitions[key] = {'canView': False}

        for key in cls._get_keys():
            key_def = cls._get_definition(key)
            if key in definitions:
                definitions[key].update(key_def)
            else:
                definitions[key] = key_def

        # Populate site.species suggested values from the ia_config
        species_json = definitions['site.species']

        from app.modules.autogenerated_names.models import AutogeneratedName

        # we kinda hack the (current-but-unstably-so) next value into the definition, so FE has a way to find it
        if 'autogenerated_names' in definitions and definitions[
            'autogenerated_names'
        ].get('value'):
            for agn_guid in definitions['autogenerated_names']['value']:
                agn = AutogeneratedName.query.get(agn_guid)
                definitions['autogenerated_names']['value'][agn_guid]['next_value'] = (
                    agn.next_value if agn else -1
                )

        from app.modules.ia_config_reader import IaConfig

        ia_config_reader = IaConfig()
        species = ia_config_reader.get_configured_species()
        if not isinstance(species_json.get('suggestedValues'), list):
            species_json['suggestedValues'] = []
        # only adds a species that is not already in suggestedValues
        for scientific_name in species:
            needed = True
            for suggestion in species_json['suggestedValues']:
                if suggestion.get('scientificName', None) == scientific_name:
                    needed = True
            if needed:
                details = ia_config_reader.get_frontend_species_summary(scientific_name)
                if details is None:
                    details = {}
                species_json['suggestedValues'].insert(
                    0,
                    {
                        'scientificName': scientific_name,
                        'commonNames': [details.get('common_name', scientific_name)],
                        'itisTsn': details.get('itis_id'),
                    },
                )

        return definitions

    # the idea here is to have a unique uuid for each installation
    #   this should be used to read this value, as it will create it if it does not exist
    @classmethod
    def get_system_guid(cls):
        val = cls.get_value('system_guid')
        if not val:
            import uuid

            val = str(uuid.uuid4())
            cls.set_key_value('system_guid', val, override_readonly=True)
        return val


# most find-based methods reference *ids* which will be guids in new-world data
# to search on name, try find_fuzzy()
class Regions(dict):
    def __init__(self, *args, **kwargs):
        if 'data' in kwargs and isinstance(kwargs['data'], dict):
            self.update(kwargs['data'])
            del kwargs['data']
        else:
            from app.modules.site_settings.models import SiteSetting

            data = SiteSetting.get_value('site.custom.regions')
            if data:
                self.update(data)
        if not len(self):
            raise ValueError('no region data available')
        super().__init__(*args, **kwargs)

    def full_path(self, loc, id_only=True):
        return self._find_path(self, loc, [], id_only)

    @classmethod
    def is_region_guid_valid(cls, guid, allow_placeholders=False):
        try:
            regions = Regions()
        except ValueError:
            # No regions so this guid (and all others) are not valid
            return False
        region_data = regions.find(guid, id_only=False)
        if (
            not allow_placeholders
            and region_data
            and region_data[0].get('placeholderOnly', False)
        ):
            return False
        return True if region_data else False

    @classmethod
    def get_region_name(cls, guid):
        region_name = None

        try:
            regions = Regions()
            region_data = regions.find(guid, id_only=False)
            if region_data:
                region_name = region_data[0].get('name', guid)
        except ValueError:
            # something went wrong presumably no region data,
            # whatever, the region name is None so just use that
            pass

        return region_name

    # as with any region-tree-traversal, this does not handle duplication of ids across nodes well.
    # first come, first served   :(
    @classmethod
    def _find_path(cls, tree, loc, path, id_only):
        if not loc:
            raise ValueError('must pass loc')
        if not tree or not isinstance(tree, dict):
            return None
        this_id = tree.get('id')
        this_data = tree.copy()
        if 'locationID' in this_data:
            del this_data['locationID']
        if this_id == loc:
            path.append(this_id if id_only else this_data)
            return path
        if 'locationID' in tree and isinstance(tree['locationID'], list):
            for sub in tree['locationID']:
                continue_path = path
                if this_id:  # skips nodes without id (e.g. top)
                    continue_path = path + [this_id if id_only else this_data]
                sub_path = cls._find_path(sub, loc, continue_path, id_only)
                if sub_path:
                    return sub_path
        return None

    def with_ancestors(self, loc_list):
        ancestors = set()
        if not loc_list or not isinstance(loc_list, list):
            return ancestors
        for loc in loc_list:
            path = self.full_path(loc)
            if path:
                ancestors.update(path)
        return ancestors

    def with_children(self, loc_list):
        if not loc_list or not isinstance(loc_list, list):
            return set()
        found = self.find(loc_list, id_only=False, full_tree=True)
        if not found:
            return set()
        children = set(loc_list)
        for match in found:
            children = set.union(children, self.node_children(match))
        return children

    @classmethod
    # note this will *not* include root node of tree
    def node_children(cls, tree):
        children = set()
        if (
            not tree
            or 'locationID' not in tree
            or not isinstance(tree['locationID'], list)
        ):
            return children
        for sub in tree['locationID']:
            if sub.get('id'):
                children.add(sub['id'])
            kid_nodes = sub.get('locationID') or []
            for kid_node in kid_nodes:
                if kid_node.get('id'):
                    children.add(kid_node['id'])
                children = set.union(children, cls.node_children(kid_node))
        return children

    def find(self, locs=None, id_only=True, full_tree=False):
        found = self._find(self, locs, id_only, full_tree)
        return set(found) if id_only else found

    @classmethod
    # full_tree only matters when id_only=False -- it will not prune subtree from node
    def _find(cls, tree, locs, id_only, full_tree):
        if not locs:
            locs = []
        elif isinstance(locs, str):
            locs = [locs]
        elif not isinstance(locs, list):
            raise ValueError('must pass string, list, or None')
        found = []
        if tree.get('id') and (not locs or tree['id'] in locs):
            if id_only:
                found.append(tree['id'])
            else:
                node_data = tree.copy()
                if not full_tree and node_data.get('locationID'):
                    del node_data['locationID']
                found.append(node_data)
        if 'locationID' in tree and isinstance(tree['locationID'], list):
            for sub in tree['locationID']:
                found = found + cls._find(sub, locs, id_only, full_tree)
        return found

    def traverse(self, node=None):
        if not node:
            return self.traverse(self)
        nodes = []
        if 'id' in node:
            nodes.append(node)
        if 'locationID' in node and isinstance(node['locationID'], list):
            for n in node['locationID']:
                nodes.extend(self.traverse(n))
        return nodes

    # finds based on old or new id
    def transfer_find(self, val):
        if not val:
            return None
        nodes = self.traverse()
        for reg in nodes:
            if reg.get('_prev_id') == val or reg.get('id') == val:
                return reg
        return None

    def find_fuzzy(self, match):
        from app.utils import fuzzy_match

        candidates = {}
        nodes = self.traverse()
        for reg in nodes:
            candidates[reg['id']] = reg.get('name', reg['id'])
        fzm = fuzzy_match(match, candidates)
        # cutoff may need some tweakage here based on experience
        if not fzm or fzm[0]['score'] < 150:
            return None
        return fzm[0]

    # pass a list, returns ordered by score all fuzzy-matches
    def find_fuzzy_list(self, possible):
        matches = []
        # reduces to unique (and lowercase first)
        for p in {a.lower() for a in possible}:
            fz = self.find_fuzzy(p)
            if fz:
                matches.append(fz)
        if not matches:
            return []
        # this way highest score (of duplicates) gets put in as only one
        once = []
        already = set()
        for m in sorted(matches, key=lambda d: -d['score']):
            if m['id'] not in already:
                once.append(m)
                already.add(m['id'])
        return once

    @classmethod
    def guidify(cls, data):
        import uuid

        if not isinstance(data, dict):
            return
        prev_id = data.get('id')
        try:
            uuid.UUID(prev_id, version=4)
        except Exception:
            data['_prev_id'] = prev_id
            data['id'] = str(uuid.uuid4())
        if 'locationID' in data and isinstance(data['locationID'], list):
            for loc in data['locationID']:
                cls.guidify(loc)
        return data

    # this will return region values *even if they are not* in site_settings! ymmv?
    @classmethod
    def usage(cls):
        from app.extensions import db

        counts = {}
        # TODO are there other places? custom-fields? etc
        tables = ['sighting', 'encounter']
        for table_name in tables:
            res = db.session.execute(
                f'SELECT location_guid, COUNT(*) FROM {table_name} GROUP BY location_guid'
            )
            for row in res:
                if row[0] in counts:
                    counts[row[0]] += row[1]
                else:
                    counts[row[0]] = row[1]
        return counts

    @classmethod
    def __repr__(self):
        return (
            f"<{self.__class__.__name__}(desc={self.get('description')} "
            f'; unique_id_count={len(self.find())})>'
        )


# constructor can take guid, scientificName, or itisTsn
class Taxonomy:
    def __init__(self, id, *args, **kwargs):
        if isinstance(id, dict):  # special case from conf value
            if not id.get('id') or not id.get('scientificName'):
                raise ValueError('dict passed with no id/scientificName')
            self.guid = id.get('id')
            self.scientificName = id.get('scientificName')
            self.itisTsn = id.get('itisTsn')
            self.commonNames = id.get('commonNames', [])
            return
        import uuid

        conf = self.get_configuration_value()
        match_value = id
        match_key = 'scientificName'
        try:
            match_value = int(id)
            match_key = 'itisTsn'
        except ValueError:
            pass
        try:
            # str() will allow us to pass in true uuid or string-representation
            uuid.UUID(str(id))
            match_value = str(id)
            match_key = 'id'
        except Exception:
            pass
        for tx in conf:
            if tx.get(match_key) == match_value:
                self.guid = tx.get('id')
                self.scientificName = tx.get('scientificName')
                self.itisTsn = tx.get('itisTsn')
                self.commonNames = tx.get('commonNames', [])
                return
        raise ValueError('unknown id')

    # this will return taxonomy_guid values *even if they are not* in site_settings! ymmv?
    @classmethod
    def usage(cls):
        from app.extensions import db

        counts = {}
        # TODO are there other places? custom-fields? etc
        # these are the places taxonomy_guid can be used:
        tables = ['individual', 'encounter', 'sighting_taxonomies']
        for table_name in tables:
            res = db.session.execute(
                f'SELECT taxonomy_guid, COUNT(*) FROM {table_name} GROUP BY taxonomy_guid'
            )
            for row in res:
                if row[0] in counts:
                    counts[row[0]] += row[1]
                else:
                    counts[row[0]] = row[1]
        return counts

    @classmethod
    def get_configuration_value(cls):
        from app.modules.site_settings.models import SiteSetting

        conf = SiteSetting.get_value('site.species')
        if not conf or not isinstance(conf, list):
            raise ValueError('site.species not configured')
        return conf

    @classmethod
    def autogen_names(cls, enabled_only=True):
        from app.modules.autogenerated_names.models import (
            AutogeneratedName,
            AutogeneratedNameType,
        )

        agns = AutogeneratedName.query.filter_by(
            type=AutogeneratedNameType.auto_species.value
        ).all()
        if not enabled_only:
            return agns
        return [a for a in agns if a.enabled]

    @classmethod
    def find_fuzzy(cls, match):
        conf = cls.get_configuration_value()
        from app.utils import fuzzy_match

        candidates = {}
        for tx in conf:
            candidates[tx['id']] = ' '.join(
                tx.get('commonNames', []) + [tx.get('scientificName')]
            )
        fzm = fuzzy_match(match, candidates)
        # cutoff may need some tweakage here based on experience
        if not fzm or fzm[0]['score'] < 120:
            return None
        tx = Taxonomy(fzm[0]['id'])
        tx._fuzz_score = fzm[0]['score']
        return tx

    # pass a list, returns ordered by score all fuzzy-matches
    @classmethod
    def find_fuzzy_list(cls, possible):
        matches = []
        # reduces to unique (and lowercase first)
        for p in {a.lower() for a in possible}:
            fz = cls.find_fuzzy(p)
            if fz:
                matches.append(fz)
        if not matches:
            return []
        # this way highest score (of duplicates) gets put in as only one
        once = []
        for m in sorted(matches, key=lambda d: -d._fuzz_score):
            if m not in once:
                once.append(m)
        return once

    def get_all_names(self):
        return self.commonNames + [self.scientificName]

    def __eq__(self, other):
        if not isinstance(other, Taxonomy):
            return False
        return self.guid == other.guid

    def __repr__(self):
        return (
            f'<{self.__class__.__name__}({self.scientificName} ' f'/ guid={self.guid})>'
        )
