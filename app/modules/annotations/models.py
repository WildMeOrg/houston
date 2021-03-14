# -*- coding: utf-8 -*-
"""
Annotations database models
--------------------
"""

from app.extensions import db, FeatherModel

import uuid


class Annotation(db.Model, FeatherModel):
    """
    Annotations database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    version = db.Column(db.BigInteger, default=None, nullable=True)

    asset_guid = db.Column(
        db.GUID,
        db.ForeignKey('asset.guid', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    asset = db.relationship('Asset', backref=db.backref('annotations'))

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def delete(self):
        with db.session.begin(subtransactions=True):
            db.session.delete(self)
