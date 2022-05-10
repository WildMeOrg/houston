# -*- coding: utf-8 -*-
"""
Progress database models
--------------------
"""
import logging

from sqlalchemy_utils import Timestamp
from etaprogress.eta import ETA

from app.extensions import db

import uuid
import enum

log = logging.getLogger(__name__)


ETA_CACHE = {}
BROKER = None
DEFAULT_CELERY_QUEUE_NAME = 'celery'


class ProgressStatus(str, enum.Enum):
    created = 'created'
    healthy = 'healthy'
    completed = 'completed'
    cancelled = 'cancelled'
    failed = 'failed'


class Progress(db.Model, Timestamp):
    """
    Progress database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    description = db.Column(db.String(length=256), nullable=False)

    percentage = db.Column(db.Integer, default=0)

    eta = db.Column(db.Float, default=None)

    celery_guid = db.Column(db.GUID, default=None)

    status = db.Column(
        db.Enum(ProgressStatus),
        default=ProgressStatus.created,
        nullable=False,
    )

    __table_args__ = (
        db.CheckConstraint(0 <= percentage, name='progress_percentage_range_min'),
        db.CheckConstraint(percentage <= 100, name='progress_percentage_range_max'),
    )

    @property
    def items(self):
        key = self._eta_cache_key()
        return ETA_CACHE[key]['items']

    @items.setter
    def items(self, value):
        global ETA_CACHE
        key = self._eta_cache_key()
        ETA_CACHE[key]['items'] = value

    @property
    def pgeta(self):
        key = self._eta_cache_key()
        return ETA_CACHE[key]['pgeta']

    @pgeta.setter
    def pgeta(self, value):
        global ETA_CACHE
        key = self._eta_cache_key()
        ETA_CACHE[key]['pgeta'] = value

    @property
    def current_eta(self):
        if self.items is None or self.pgeta is None:
            return None
        if self.pgeta.eta_seconds is None:
            return None
        else:
            return round(self.pgeta.eta_seconds, 1)

    @property
    def complete(self):
        return (
            self.status in [ProgressStatus.healthy, ProgressStatus.completed]
            and self.percentage >= 100
        )

    @property
    def ahead(self):
        import redis
        import json

        global BROKER

        from flask import current_app

        if self.celery_guid is None:
            return None

        if BROKER is None:
            BROKER = redis.Redis(
                host=current_app.config['REDIS_HOST'],
                port=current_app.config['REDIS_PORT'],
                db=current_app.config['REDIS_DATABASE'],
                password=current_app.config['REDIS_PASSWORD'],
            )

        # inspect = current_app.celery.control.inspect()
        # workers = inspect.ping()

        total = BROKER.llen(DEFAULT_CELERY_QUEUE_NAME)
        if total is None:
            total = 0

        for index in range(total):
            try:
                message = BROKER.lindex(DEFAULT_CELERY_QUEUE_NAME, index)
                data = json.loads(message)
                celery_guid = data.get('headers', {}).get('id', None)
                if celery_guid is not None:
                    celery_guid = uuid.UUID(celery_guid)
                    if celery_guid == self.celery_guid:
                        return total - 1 - index
            except Exception:
                pass

        return 0

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'description=\'{self.description}\', '
            'status={self.status}, '
            'percentage={self.percentage}, '
            'eta={self.eta}, '
            'complete={self.complete}, '
            'created={self.created}, '
            'updated={self.updated}'
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def __iter__(self):
        assert (
            self.items is not None and self.pgeta is not None
        ), 'Items is not configured, use obj = obj.config(items) to setup'
        self.pgeta.numerator = 0
        self.set(0, force=True)
        return self

    def __next__(self):
        try:
            return self.item(autoiterate=True)
        except (ValueError, IndexError):
            raise StopIteration

    def _eta_cache_key(self):
        global ETA_CACHE
        # key = '%s:%s' % (self.guid, id(a), )
        key = str(self.guid)
        if key not in ETA_CACHE:
            ETA_CACHE[key] = {
                'items': None,
                'pgeta': None,
            }
        return key

    def is_public(self):
        return True

    @db.validates('description')
    def validate_description(
        self, key, description
    ):  # pylint: disable=unused-argument,no-self-use
        if len(description) < 3:
            raise ValueError('description has to be at least 3 characters long.')
        return description

    def fail(self):
        db.session.refresh(self)
        if self.status not in [ProgressStatus.created, ProgressStatus.healthy]:
            return
        with db.session.begin(subtransactions=True):
            self.status = ProgressStatus.failed
            db.session.merge(self)
        db.session.refresh(self)

    def cancel(self):
        db.session.refresh(self)
        if self.status not in [ProgressStatus.created, ProgressStatus.healthy]:
            return
        with db.session.begin(subtransactions=True):
            self.status = ProgressStatus.cancelled
            db.session.merge(self)
        db.session.refresh(self)

    def delete(self):
        with db.session.begin(subtransactions=True):
            db.session.delete(self)

    def config(self, items=None):
        if items is None:
            items = list(range(1, 101))

        assert isinstance(items, (tuple, list))
        self.items = items

        total = len(self.items)
        self.pgeta = ETA(total)

        assert self.pgeta.numerator == 0
        assert self.pgeta.denominator == total

        self.set(0, force=True)

        assert self.items is not None
        assert self.pgeta is not None

        return self

    def reset(self):
        global ETA_CACHE
        key = self._eta_cache_key()
        ETA_CACHE.pop(key, None)

    def item(self, autoiterate=False):
        if self.items is None or self.pgeta is None:
            self.reset()
            raise ValueError(
                'Items is not configured, use obj = obj.config(items) to setup'
            )

        if self.pgeta.numerator >= len(self.items):
            self.reset()
            raise IndexError('Items have been exhausted')

        assert self.pgeta.numerator >= 0
        assert self.pgeta.numerator < len(self.items)

        item = self.items[self.pgeta.numerator]

        if autoiterate:
            self.iterate()

        return item

    def iterate(self, amount=1):
        self.pgeta.numerator += amount
        self.set(100.0 * self.pgeta.numerator / len(self.items))

    def increment(self, amount=1):
        self.set(self.percentage + amount)

    def set(self, value, items=None, force=False):
        new_percentage = int(max(0, min(100, value)))

        db.session.refresh(self)
        if self.status not in [ProgressStatus.created, ProgressStatus.healthy]:
            log.warning(
                'Attempting to set Progress %r to %d, but status is %r'
                % (
                    self.guid,
                    new_percentage,
                    self.status,
                )
            )
            return self.status

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
                return 'ignored'

        if self.items is None or self.pgeta is None:
            self = self.config(items=items)

        assert self.pgeta is not None

        if int(self.pgeta.percent) < new_percentage:
            self.pgeta.numerator = int(self.pgeta.denominator * (new_percentage / 100.0))
            # assert int(self.pgeta.percent) >= new_percentage

        with db.session.begin(subtransactions=True):
            self.percentage = new_percentage
            self.eta = self.current_eta
            if self.percentage >= 100:
                self.status = ProgressStatus.completed
                self.reset()
            else:
                self.status = ProgressStatus.healthy
            db.session.merge(self)
        db.session.refresh(self)

        log.info('Updated %r' % (self,))

        return 'set'
