# -*- coding: utf-8 -*-
"""
Individuals database models
--------------------
"""

from sqlalchemy_utils import Timestamp

from app.extensions import db

import uuid


class Individual(db.Model, Timestamp):
    """
    Individuals database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'title=\'{self.title}\''
            ')>'.format(
                class_name=self.__class__.__name__,
                self=self
            )
        )
