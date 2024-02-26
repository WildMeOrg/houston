# -*- coding: utf-8 -*-
"""
Keywords database models
--------------------
"""
import enum
import logging
import uuid

from app.extensions import HoustonModel, db

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

    @classmethod
    def ensure_keyword(cls, value, source=None, create=True):
        # Check if we have received a dictionary, if so, call it as arguments
        if isinstance(value, dict):
            assert source is None
            value['create'] = True
            return cls.ensure_keyword(**value)

        # If a source is not provided, use the default
        if source is None:
            source = KeywordSource.user

        assert value is not None, 'The value for a Keyword cannot be missing'
        assert source is not None, 'The source for a Keyword must be specified'
        keyword = cls.query.filter_by(value=value, source=source).first()

        # If the keyword is not found, let's double check that the user didn't specify the GUID as the value
        if keyword is None:
            try:
                keyword = cls.query.get(value)
            except Exception:
                pass

        # If we still haven't found it, make it and return keyword
        if keyword is None and create:
            with db.session.begin(subtransactions=True):
                keyword = cls(
                    value=value,
                    source=source,
                )
                db.session.add(keyword)
            db.session.refresh(keyword)

        return keyword

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

    def merge(self, other):
        # self.guid is the traget_keyword.guid
        # other.guid is the source_keyword.guid
        # the goal of this function is to merge the source_keyword into the target_keyword
        # and update all the references to the source_keyword to point to the target_keyword
        # and then delete the source_keyword
        # A keyword can be referenced by annotations and assets
        # When a keyword is merged, all the references to the source_keyword should be updated to point to the target_keyword

        # Import necessary modules
        from app.modules.annotations.models import AnnotationKeywords
        from app.modules.assets.models import AssetTags

        # Get and update all the annotations that reference the other keyword
        ref_annos = AnnotationKeywords.query.filter_by(keyword_guid=other.guid).all()
        for ref_ann in ref_annos:
            ref_ann.keyword_guid = self.guid

        # Get and update all the assets that reference the other keyword
        ref_assets = AssetTags.query.filter_by(tag_guid=other.guid).all()
        for ref_asset in ref_assets:
            ref_asset.tag_guid = self.guid

        # Delete the other keyword
        other.delete()

        try:
            updated_ref_ann = AnnotationKeywords.query.filter_by(keyword_guid=self.guid).first()
            if updated_ref_ann.keyword_guid == self.guid:
                log.info("The annotation's keyword_guid has been successfully updated.")
            else:
                log.info("The update did not take place as expected.")
        except Exception as e:
            log.info(f"Error during merge commit: {e}")