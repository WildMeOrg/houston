# -*- coding: utf-8 -*-
"""
Site Settings database models
--------------------
"""
from app.extensions import db, Timestamp, extension_required, is_extension_enabled
from flask import current_app


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
                f'forbidden to directly set key with prefix "{EDM_PREFIX}" via SiteSetting (key={key})'
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
    def get_string(cls, key, default=None):
        setting = cls.query.get(key)
        return setting.string if setting else default

    @classmethod
    def get_json(cls, key, default=None):
        setting = cls.query.get(key)
        return setting.data if setting else default

    # a bit of hackery.  right now *all* keys in edm-configuration are of the form `site.foo` so we use
    #   as a way branch on _where_ to get the value to return here.  but as we ween ourselves off edm config,
    #   this can hopefully be backwards compatible
    @classmethod
    def get_value(cls, key, **kwargs):
        if not key:
            raise ValueError('key must not be None')
        if is_extension_enabled('edm') and key.startswith(EDM_PREFIX):
            return cls.get_edm_configuration(key, **kwargs)
        setting = cls.query.get(key)
        if not setting:
            return kwargs['default'] if 'default' in kwargs else None
        if setting.file_upload_guid:
            return setting.file_upload
        return setting.string

    @classmethod
    @extension_required('edm')
    def get_edm_configuration(cls, key, **kwargs):
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
        if (
            'valueNotSet' in res['response']
            and res['response']['valueNotSet']
            and 'default' in kwargs
        ):
            return kwargs['default']
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
