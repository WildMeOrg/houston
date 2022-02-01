# -*- coding: utf-8 -*-
"""
Keywords database models
--------------------
"""
import enum
import logging
import uuid

from app.extensions import db, HoustonModel

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class KeywordSource(str, enum.Enum):
    user = 'user'
    wbia = 'wbia'


# class KeywordModule(str, enum.Enum):
#     annotation = 'annotation'
#     asset = 'asset'


class Keyword(db.Model, HoustonModel):
    """
    Keywords database model.
    """

    __mapper_args__ = {
        'confirm_deleted_rows': False,
    }

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
    # module = db.Column(
    #     db.Enum(KeywordModule),
    #     default=KeywordModule.user,
    #     index=True,
    #     nullable=False,
    # )

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

    def __lt__(self, other):
        return self.value < other.value

    def delete(self):
        with db.session.begin(subtransactions=True):
            db.session.delete(self)

    def delete_if_unreferenced(self):
        if self.number_referenced_dependencies() < 1:
            log.warning(
                f'{self} is no longer referenced by any Annotation or Asset, deleting.'
            )
            self.delete()

    def number_referenced_dependencies(self):
        from app.modules.annotations.models import AnnotationKeywords
        from app.modules.assets.models import AssetTags

        refs = []
        refs += AnnotationKeywords.query.filter_by(keyword_guid=self.guid).all()
        refs += AssetTags.query.filter_by(tag_guid=self.guid).all()
        return len(refs)
