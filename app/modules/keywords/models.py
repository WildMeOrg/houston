# -*- coding: utf-8 -*-
"""
Keywords database models
--------------------
"""

from app.extensions import db, HoustonModel

import uuid
import enum
import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class KeywordSource(str, enum.Enum):
    user = 'user'
    wbia = 'wbia'


class Keyword(db.Model, HoustonModel):
    """
    Keywords database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    value = db.Column(db.String, nullable=False, unique=True)
    source = db.Column(
        db.Enum(KeywordSource),
        default=KeywordSource.user,
        index=True,
        nullable=False,
    )

    def get_value(self):
        return self.value

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'value={self.value}, '
            'source={self.source}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def delete(self):
        with db.session.begin(subtransactions=True):
            db.session.delete(self)

    def delete_if_unreferenced(self):
        if self.number_annotations() < 1:
            log.warn(f'{self} is no longer referenced by any Annotation, deleting.')
            self.delete()

    def number_annotations(self):
        from app.modules.annotations.models import AnnotationKeywords

        refs = AnnotationKeywords.query.filter_by(keyword_guid=self.guid).all()
        return len(refs)
