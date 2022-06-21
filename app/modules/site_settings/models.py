# -*- coding: utf-8 -*-
"""
Site Settings database models
--------------------
"""
import logging

from flask import current_app
from flask_login import current_user  # NOQA

from app.extensions import Timestamp, db, extension_required, is_extension_enabled
from app.modules import is_module_enabled
from app.utils import HoustonException

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
        'social_group_roles': {'type': list, 'public': True},
        'relationship_type_roles': {
            'type': dict,
            'public': True,
            'definition': {
                'fieldType': 'json',
                'displayType': 'relationship-type-role',
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
    def set(
        cls,
        key,
        file_upload_guid=None,
        string=None,
        public=None,
        data=None,
        boolean=None,
        override_readonly=False,
    ):
        if is_extension_enabled('edm') and cls._is_edm_key(key):
            raise ValueError(f'forbidden to directly set key {key}')
        key_conf = cls._get_houston_setting_conf(key)
        if key_conf.get('read_only', False) and not override_readonly:
            raise ValueError(f'read-only key {key}')

        kwargs = {
            'key': key,
            'file_upload_guid': file_upload_guid,
            'string': string,
            'data': data,
            'boolean': boolean,
        }
        if public is not None:
            kwargs['public'] = public
        setting = cls(**kwargs)
        with db.session.begin(subtransactions=True):
            return db.session.merge(setting)

    @classmethod
    def get_setting_keys(cls):
        return cls.HOUSTON_SETTINGS.keys()

    @classmethod
    def is_houston_only_setting(cls, key):
        return key in cls.HOUSTON_SETTINGS.keys()

    @classmethod
    def _get_houston_setting_conf(cls, key):
        if cls.is_houston_only_setting(key):
            return cls.HOUSTON_SETTINGS[key]
        else:
            return {}

    @classmethod
    def _get_value_for_edm_formats(cls, key):
        value = cls.get_value(key)
        key_conf = cls._get_houston_setting_conf(key)

        # Only admin can read private data
        if not key_conf.get('public', True):
            if not current_user or current_user.is_anonymous or not current_user.is_admin:
                value = None
        return value

    @classmethod
    def get_value_verbose(cls, key):
        value = cls._get_value_for_edm_formats(key)
        value_not_set = value is None

        data = {
            'value': value if not value_not_set else cls._get_default_value(key),
        }
        return data

    @classmethod
    def get_houston_definitions(cls):
        configuration = {}
        for key in SiteSetting.get_setting_keys():
            configuration[key] = cls.get_definition(key)
        return configuration

    @classmethod
    def get_definition(cls, key):
        key_conf = cls._get_houston_setting_conf(key)
        is_public = key_conf.get('public', True)
        data = {
            'descriptionId': f'CONFIGURATION_{key.upper()}_DESCRIPTION',
            'labelId': f'CONFIGURATION_{key.upper()}_LABEL',
            'defaultValue': '',
            'isPrivate': not is_public,
            'settable': True,
            'required': True,
            'fieldType': 'string',
            'displayType': 'string',
        }
        value = cls._get_value_for_edm_formats(key)
        if value:
            data['currentValue'] = value

        # Some variables have specific values so incorporate those as required
        edm_definition = key_conf.get('definition', None)
        if edm_definition:
            data.update(edm_definition)
        return data

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
        if cls.HOUSTON_SETTINGS[key]['type'] == bool:
            def_val = False
        return def_val

    @classmethod
    def validate_social_group_roles(cls, value):
        if is_module_enabled('social_groups'):
            from app.modules.social_groups.models import SocialGroup

            SocialGroup.validate_roles(value)

    @classmethod
    def validate_relationship_type_roles(cls, value):
        if not isinstance(value, dict):
            raise HoustonException(
                log, 'relationship_type_roles needs to be a dictionary'
            )

        from .schemas import RelationshipTypeSchema

        schema = RelationshipTypeSchema()
        for relationship_object in value.values():
            errors = schema.validate(relationship_object)
            if errors:
                raise HoustonException(log, schema.get_error_message(errors))

    @classmethod
    def set_houston_data(cls, data):
        assert isinstance(data, dict)
        success_keys = []
        for key in data.keys():
            if key in cls.get_setting_keys():
                if data[key] is not None:
                    cls.set_key_value(key, data[key])
                else:
                    cls.forget_key_value(key)
                success_keys.append(key)

        return success_keys

    @classmethod
    def set_key_value(cls, key, value):
        if callable(getattr(cls, f'validate_{key}', None)):
            # should raise HoustonException if validation fails
            getattr(cls, f'validate_{key}')(value)

        assert key in cls.HOUSTON_SETTINGS.keys()
        if not isinstance(value, cls.HOUSTON_SETTINGS[key]['type']):
            msg = f'Houston Setting key={key}, value incorrect type value={value},'
            msg += f'needs to be {cls.HOUSTON_SETTINGS[key]["type"]}'
            raise HoustonException(log, msg)

        if isinstance(value, str):
            log.debug(f'updating Houston Setting key={key}')
            cls.set(key, string=value, public=cls.HOUSTON_SETTINGS[key]['public'])
        elif isinstance(value, dict) or isinstance(value, list):
            log.debug(f'updating Houston Setting key={key}')
            cls.set(key, data=value, public=cls.HOUSTON_SETTINGS[key]['public'])
        elif isinstance(value, bool):
            log.debug(f'updating Houston Setting key={key}')
            cls.set(key, boolean=value, public=cls.HOUSTON_SETTINGS[key]['public'])
        else:
            msg = f'Houston Setting key={key}, value is not string, list or dict; value={value}'
            raise HoustonException(log, msg)

        if key == 'social_group_roles' and is_module_enabled('social_groups'):
            from app.modules.social_groups.models import SocialGroup

            SocialGroup.site_settings_updated()

    @classmethod
    def forget_key_value(cls, key):
        if cls._is_edm_key(key) and is_extension_enabled('edm'):
            # Only support removal of EDM keys that start with 'site.custom.customFields' and end with '/{guid}'

            edm_path_parts = key.split('/')
            if len(edm_path_parts) != 2:
                raise HoustonException(log, f'removal of {key} not supported')

            name = edm_path_parts[0]
            guid = edm_path_parts[1]
            try:
                # this is just to test it is a valid uuid - will throw ValueError if not
                from uuid import UUID

                UUID(guid, version=4)
            except ValueError:
                raise HoustonException(
                    log, f'removal of {key} not supported, guid not valid'
                )
            if not name.startswith('site.custom.customFields'):
                raise HoustonException(
                    log, 'Ony support removal of EDM site.custom.customFields entries'
                )
            changed, name = cls._map_to_deprecated_edm_key(name)
            if changed:
                key = f'{name}/{guid}'
            patch_data = {'force': False, 'op': 'remove', 'path': key}
            cls._patch_edm_configuration({'json': patch_data})

        else:
            setting = cls.query.get(key)
            if setting:
                with db.session.begin(subtransactions=True):
                    db.session.delete(setting)

                if key == 'social_group_roles' and is_module_enabled('social_groups'):
                    from app.modules.social_groups.models import SocialGroup

                    SocialGroup.site_settings_updated()

    @classmethod
    def get_string(cls, key, default=None):
        setting = cls.query.get(key)
        if not setting and default is None:
            return cls._get_default_value(key)
        return setting.string if setting else default

    @classmethod
    def get_json(cls, key, default=None):
        setting = cls.query.get(key)
        if not setting and default is None:
            return cls._get_default_value(key)
        return setting.data if setting else default

    @classmethod
    def get_boolean(cls, key, default=None):
        setting = cls.query.get(key)
        if not setting and default is None:
            return cls._get_default_value(key)
        return setting.boolean if setting else default

    @classmethod
    def _is_edm_key(cls, key):
        return not cls.is_houston_only_setting(key)

    @classmethod
    def get_value(cls, key, default=None, **kwargs):
        if not key:
            raise ValueError('key must not be None')
        if is_extension_enabled('edm') and cls._is_edm_key(key):
            return cls._get_edm_value(key, default=default, **kwargs)
        setting = cls.query.get(key)
        if not setting:
            setting_default = cls._get_default_value(key)
            if default is None and setting_default:
                if callable(setting_default):
                    setting_default = setting_default()
                return setting_default
            return default
        if setting.file_upload_guid:
            return setting.file_upload
        elif setting.data:
            return setting.data
        elif setting.boolean is not None:
            return setting.boolean
        return setting.string

    @classmethod
    def get_houston_block_data_for_current_user(cls):
        from flask import url_for

        from app.modules.users.models import User

        values = {'site.adminUserInitialized': User.admin_user_initialized()}

        # Create the site.images
        houston_settings = SiteSetting.query.filter_by(public=True).order_by('key')
        site_images = {}
        for setting in houston_settings:
            if setting.file_upload is not None:
                site_images[setting.key] = url_for(
                    'api.fileuploads_file_upload_src_u_by_id_2',
                    fileupload_guid=str(setting.file_upload.guid),
                    _external=False,
                )
        values['site.images'] = site_images

        is_admin = getattr(current_user, 'is_admin', False)
        for key, type_def in SiteSetting.HOUSTON_SETTINGS.items():
            permission = type_def.get('permission', lambda: True)()
            if is_admin or type_def.get('public', True) and permission:
                values[key] = SiteSetting.get_value_verbose(key)
        return values

    # MainConfiguration and MainConfigurationDefinition resources code needs to behave differently if it's
    # accessing a block of data or a single value, so have one place that does this check
    @classmethod
    def is_block_key(cls, key):
        changed, new_key = cls._map_to_deprecated_edm_key(key)
        return new_key == '__bundle_setup'

    # Deprecating the support opf the old Occurrence and MarkedIndividual fields to replace with Sighting and
    # Individual but support both until EDM is retired, mapping the new names to the old names
    @classmethod
    def _map_to_deprecated_edm_key(cls, key):
        if key == 'block':
            return True, '__bundle_setup'
        elif key == 'site.custom.customFields.Sighting':
            return True, 'site.custom.customFields.Occurrence'
        elif key == 'site.custom.customFields.Individual':
            return True, 'site.custom.customFields.MarkedIndividual'
        return False, key

    # mapping backwards
    @classmethod
    def _map_to_new_key(cls, key):
        if key == 'site.custom.customFields.Occurrence':
            return True, 'site.custom.customFields.Sighting'
        elif key == 'site.custom.customFields.MarkedIndividual':
            return True, 'site.custom.customFields.Individual'
        return False, key

    @classmethod
    @extension_required('edm')
    def _get_edm_value(cls, key, default=None, **kwargs):
        # There are certain fields that are Old Wildbook specific that we still support for the moment but
        # will be deprecated so allow gets of both old and new (and map the new to the old here)
        changed, key = cls._map_to_deprecated_edm_key(key)

        res = current_app.edm.get_dict('configuration.data', key)
        if (
            not isinstance(res, dict)
            or not res['success']
            or 'response' not in res
            or 'value' not in res['response']
        ):
            raise ValueError(
                f'invalid EDM configuration key {key} (status {res.status_code})'
            )
        # edm conf lets us know if there is no value set like this:
        if 'valueNotSet' in res['response'] and res['response']['valueNotSet']:
            return default
            # if no default= via kwargs it falls thru to below, which is fine (edm picks default value)
        return res['response']['value']

    @classmethod
    def get_edm_configuration_as_edm_format(cls, dict_name, path):
        changed, edm_key = cls._map_to_deprecated_edm_key(path)
        data = current_app.edm.get_dict(
            dict_name,
            edm_key,
            target='default',
        )

        # For the deprecated fields from EDM, also add the new names if it's the block get
        if (
            cls.is_block_key(path)
            and isinstance(data, dict)
            and data['success']
            and 'response' in data
            and 'configuration' in data['response']
        ):
            import copy

            config = copy.deepcopy(data['response']['configuration'])
            data['response']['configuration'].keys()
            for key in data['response']['configuration'].keys():
                changed, new_key = cls._map_to_new_key(key)
                if changed and 'value' in config[key].keys():
                    old_config_value = config[key]['value']
                    config[key] = {}
                    config[key]['value'] = old_config_value
                    config[new_key] = old_config_value

                elif 'value' in config[key].keys() and key != 'site.species':
                    old_config_value = config[key]['value']
                    config[key] = {}
                    config[key]['value'] = old_config_value
                elif key != 'site.species':
                    config[key] = {}

            data['response']['configuration'] = config

        # simplify this by only sending back the fields that the FE actually uses
        returned_data = {
            'response': {
                'version': data['response']['version'],
                'configuration': data['response']['configuration'],
            }
        }
        return returned_data

    @classmethod
    def post_edm_configuration(cls, path, kwargs):
        if path == 'block' or path == '':
            # Use edm value for block
            path = ''
            if isinstance(kwargs, dict) and 'data' in kwargs:
                import copy

                config = copy.deepcopy(kwargs['data'])
            for key in kwargs['data']:
                changed, edm_key = cls._map_to_deprecated_edm_key(key)
                if changed:
                    config[edm_key] = config[key]
                    config.pop(key)
            kwargs['data'] = config
        else:
            changed, path = cls._map_to_deprecated_edm_key(path)

        response = current_app.edm.request_passthrough(
            'configuration.data',
            'post',
            kwargs,
            path,
            target='default',
        )

        if not response.ok or response.status_code != 200:
            raise HoustonException(
                log,
                f'non-OK ({response.status_code}) response from edm: {response.json()}',
            )

        return response

    @classmethod
    def _patch_edm_configuration(cls, kwargs):
        response = current_app.edm.request_passthrough(
            'configuration.data',
            'patch',
            kwargs,
            '',
            target='default',
        )

        if not response.ok or response.status_code != 200:
            raise HoustonException(
                log,
                f'non-OK ({response.status_code}) response from edm: {response.json()}',
            )

        return response

    # the idea here is to have a unique uuid for each installation
    #   this should be used to read this value, as it will create it if it does not exist
    @classmethod
    def get_system_guid(cls):
        val = cls.get_string('system_guid')
        if not val:
            import uuid

            val = str(uuid.uuid4())
            cls.set('system_guid', string=val, public=True, override_readonly=True)
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

    @classmethod
    def get_configuration_value(cls):
        from app.modules.site_settings.models import SiteSetting

        conf = SiteSetting.get_value('site.species')
        if not conf or not isinstance(conf, list):
            raise ValueError('site.species not configured')
        return conf

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
