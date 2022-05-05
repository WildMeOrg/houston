# -*- coding: utf-8 -*-
"""
Progress database models
--------------------
"""
import logging

from sqlalchemy_utils import Timestamp

from app.extensions import db

import uuid

log = logging.getLogger(__name__)


class Progress(db.Model, Timestamp):
    """
    Progress database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    description = db.Column(db.String(length=256), nullable=False)

    percentage = db.Column(db.Integer, default=0)

    __table_args__ = (
        db.CheckConstraint(0 <= percentage, name='progress_percentage_range_min'),
        db.CheckConstraint(percentage <= 100, name='progress_percentage_range_max'),
    )

    items = None
    index = None

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'description=\'{self.description}\', '
            'percentage={self.percentage}, '
            'created={self.created}, '
            'updated={self.updated}'
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def __iter__(self):
        assert (
            self.items is not None
        ), 'Items is not configured, use obj = obj.items(items) to setup'
        self.index = 0
        self.set(0, force=True)
        return self

    def __next__(self):
        try:
            item = self.item()
        except (ValueError, IndexError):
            raise StopIteration

        self.iterate()

        return item

    def is_public(self):
        return True

    @property
    def complete(self):
        return self.percentage >= 100

    @db.validates('description')
    def validate_description(
        self, key, description
    ):  # pylint: disable=unused-argument,no-self-use
        if len(description) < 3:
            raise ValueError('description has to be at least 3 characters long.')
        return description

    def items(self, items):
        assert isinstance(items, (tuple, list))
        self.items = items
        self.index = 0
        self.set(0, force=True)
        return self

    def item(self, autoiterate=False):
        if self.items is None or self.index is None:
            self.items = None
            self.index = None
            raise ValueError(
                'Items is not configured, use obj = obj.items(items) to setup'
            )

        if self.index >= len(self.items):
            self.items = None
            self.index = None
            raise IndexError('Items have been exhausted')

        assert self.index >= 0
        assert self.index < len(self.items)

        item = self.items[self.index]

        if autoiterate:
            self.iterate()

        return item

    def iterate(self, amount=1):
        self.index += amount
        self.set(100.0 * self.index / len(self.items))

    def increment(self, amount=1):
        self.set(self.percentage + amount)

    def set(self, value, force=False):
        new_percentage = int(max(0, min(100, round(value))))
        if new_percentage < self.percentage:
            if not force:
                log.warning(
                    'Attempting to decrement Progress %r from %d to %d, ignored (set force=True to override)'
                    % (
                        self.guid,
                        self.percentage,
                        new_percentage,
                    )
                )
                return

        with db.session.begin():
            self.percentage = new_percentage
            db.session.merge(self)
