# -*- coding: utf-8 -*-
"""
Site Settings database models
--------------------
"""
from app.extensions import db, Timestamp


class SiteSetting(db.Model, Timestamp):
    """
    Site Settings database model.
    """

    key = db.Column(db.String, primary_key=True, nullable=False)

    file_upload_guid = db.Column(
        db.GUID, db.ForeignKey('file_upload.guid', ondelete='CASCADE'), nullable=True
    )
    file_upload = db.relationship('FileUpload', cascade='delete')
    public = db.Column(db.Boolean, default=True, nullable=False)
    string = db.Column(db.String, default='', nullable=True)

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}(key='{self.key}' "
            f"file_upload_guid='{self.file_upload_guid}' "
            f'public={self.public})>'
        )

    def is_public(self):
        return self.public

    @classmethod
    def set(cls, key, file_upload_guid=None, string=None, public=None):
        kwargs = {
            'key': key,
            'file_upload_guid': file_upload_guid,
            'string': string,
        }
        if public is not None:
            kwargs['public'] = public
        setting = cls(**kwargs)
        with db.session.begin(subtransactions=True):
            return db.session.merge(setting)

    @classmethod
    def get_string(cls, key):
        ss = cls.query.get(key)
        return ss.string if ss else None
