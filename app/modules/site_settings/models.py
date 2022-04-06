# -*- coding: utf-8 -*-
"""
Site Settings database models
--------------------
"""
from app.extensions import db, Timestamp, extension_required, is_extension_enabled
from flask import current_app
from flask_login import current_user  # NOQA

from app.modules import is_module_enabled
from app.utils import HoustonException

import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name

# these will be disallowed to be set via api (must be done elsewhere in code by using override_readonly)
READ_ONLY = 'system_guid'
EDM_PREFIX = 'site.'


class SiteSetting(db.Model, Timestamp):
    """
    Site Settings database model.
    """

    __mapper_args__ = {
        'confirm_deleted_rows': False,
    }

    HOUSTON_SETTINGS = {
        'email_service': {
            'type': str,
            'public': False,
            'edm_definition': {
                'defaultValue': '',
                'displayType': 'select',
                'schema': {
                    'choices': [
                        {'label': 'Do not send mail', 'value': ''},
                        {'label': 'Mailchimp/Mandrill', 'value': 'mailchimp'},
                    ]
                },
            },
        },
        'email_service_username': {'type': str, 'public': False},
        'email_service_password': {'type': str, 'public': False},
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
            'public': True,
        },
        'email_title_greeting': {
            'type': str,
            'public': True,
            'default': 'Hello!',
        },
        'email_secondary_title': {
            'type': str,
            'public': True,
            'default': 'Codex for everyone!',
        },
        'email_secondary_text': {
            'type': list,
            'public': True,
            'default': [
                'Can you help researchers study and protect animals?',
                'Wild Me is a 501(c)(3) non-profit that develops the cutting edge technology for a global community of wildlife researchers. Are you interested in further supporting our mission?',
            ],
        },
        'email_adoption_button_text': {
            'type': str,
            'public': True,
            'default': 'Adopt an animal',
        },
        'email_legal_statement': {
            'type': str,
            'public': True,
            'default': 'Wildbook is copyrighted 2022 by Wild Me.  Individual contributors to Wildbook retain copyrights for submitted images. No reproduction or usage of material in this library is permitted without the express permission of the copyright holders.',
        },
        'social_group_roles': {'type': list, 'public': True},
        'relationship_type_roles': {
            'type': dict,
            'public': True,
            'edm_definition': {
                'fieldType': 'json',
                'displayType': 'relationship-type-role',
                'required': False,
            },
        },
    }

    key = db.Column(db.String, primary_key=True, nullable=False)

    file_upload_guid = db.Column(
        db.GUID, db.ForeignKey('file_upload.guid', ondelete='CASCADE'), nullable=True
    )
    file_upload = db.relationship('FileUpload', cascade='delete')
    public = db.Column(db.Boolean, default=True, nullable=False)
    string = db.Column(db.String, default='', nullable=True)
    data = db.Column(db.JSON, nullable=True)

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
        override_readonly=False,
    ):
        if is_extension_enabled('edm') and key.startswith(EDM_PREFIX):
            raise ValueError(
                f'forbidden to directly set key with prefix "{EDM_PREFIX}" via (key={key})'
            )
        if key in READ_ONLY and not override_readonly:
            raise ValueError(f'read-only key {key}')
        kwargs = {
            'key': key,
            'file_upload_guid': file_upload_guid,
            'string': string,
            'data': data,
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
    def _get_value_for_edm_formats(cls, key):
        assert key in cls.HOUSTON_SETTINGS.keys()
        value = cls.get_value(key)

        # Only admin can read private data
        if not cls.HOUSTON_SETTINGS[key]['public']:
            if not current_user or current_user.is_anonymous or not current_user.is_admin:
                value = None
        return value

    @classmethod
    def get_as_edm_format(cls, key):
        assert key in cls.HOUSTON_SETTINGS.keys()
        value = cls._get_value_for_edm_formats(key)

        data = {
            'id': key,
            'isSiteSetting': True,
            'value': value if value else cls._get_default_value(key),
            'valueNotSet': value is None,
        }
        return data

    @classmethod
    def get_as_edm_definition_format(cls, key):
        assert key in cls.HOUSTON_SETTINGS.keys()
        value = cls._get_value_for_edm_formats(key)

        data = {
            'descriptionId': f'CONFIGURATION_{key.upper()}_DESCRIPTION',
            'labelId': f'CONFIGURATION_{key.upper()}_LABEL',
            'defaultValue': '',
            'isPrivate': not cls.HOUSTON_SETTINGS[key]['public'],
            'settable': True,
            'required': True,
            'fieldType': 'string',
            'displayType': 'string',
        }
        if value:
            data['currentValue'] = value

        # Some variables have specific values so incorporate those as required
        if 'edm_definition' in cls.HOUSTON_SETTINGS[key].keys():
            data.update(cls.HOUSTON_SETTINGS[key]['edm_definition'])
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
        return def_val

    @classmethod
    def set_key_value(cls, key, value):
        if key == 'social_group_roles' and is_module_enabled('social_groups'):
            from app.modules.social_groups.models import SocialGroup

            # raises houston exception on failure
            SocialGroup.validate_roles(value)

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
        else:
            msg = f'Houston Setting key={key}, value is not string, list or dict; value={value}'
            raise HoustonException(log, msg)

        if key == 'social_group_roles' and is_module_enabled('social_groups'):
            from app.modules.social_groups.models import SocialGroup

            SocialGroup.site_settings_updated()

    @classmethod
    def forget_key_value(cls, key):
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

    # a bit of hackery.  right now *all* keys in edm-configuration are of the form `site.foo` so we use
    #   as a way branch on _where_ to get the value to return here.  but as we ween ourselves off edm config,
    #   this can hopefully be backwards compatible
    @classmethod
    def get_value(cls, key, default=None, **kwargs):
        if not key:
            raise ValueError('key must not be None')
        if is_extension_enabled('edm') and key.startswith(EDM_PREFIX):
            return cls.get_edm_configuration(key, default=default, **kwargs)
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
        return setting.string

    @classmethod
    @extension_required('edm')
    def get_edm_configuration(cls, key, default=None, **kwargs):
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


class Regions(dict):
    def __init__(self, *args, **kwargs):
        if 'data' in kwargs and isinstance(kwargs['data'], dict):
            self.update(kwargs['data'])
            del kwargs['data']
        else:
            from app.modules.site_settings.models import SiteSetting

            data = SiteSetting.get_edm_configuration('site.custom.regions')
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

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}(desc={self.get('description')} "
            f'; unique_id_count={len(self.find())})>'
        )
