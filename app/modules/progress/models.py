# -*- coding: utf-8 -*-
"""
Progress database models
--------------------
"""
import enum
import logging
import uuid

from etaprogress.eta import ETA
from sqlalchemy_utils import Timestamp

from app.extensions import db

log = logging.getLogger(__name__)


ETA_CACHE = {}
BROKER = None
DEFAULT_CELERY_QUEUE_NAME = 'celery'


class ProgressStatus(str, enum.Enum):
    created = 'created'
    healthy = 'healthy'
    completed = 'completed'
    skipped = 'skipped'
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

    sage_guid = db.Column(db.GUID, default=None)

    message = db.Column(db.String, nullable=True)

    status = db.Column(
        db.Enum(ProgressStatus),
        default=ProgressStatus.created,
        nullable=False,
    )

    parent_guid = db.Column(
        db.GUID, db.ForeignKey('progress.guid'), index=True, nullable=True
    )
    steps = db.relationship(
        'Progress',
        backref=db.backref(
            'parent',
            primaryjoin='Progress.guid == Progress.parent_guid',
            cascade='all',
            remote_side=guid,
        ),
        remote_side=parent_guid,
    )

    __mapper_args__ = {
        'confirm_deleted_rows': False,
    }

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
    def idle(self):
        return self.status in [ProgressStatus.created]

    @property
    def skipped(self):
        return self.status in [ProgressStatus.skipped]

    @property
    def cancelled(self):
        return self.status in [ProgressStatus.cancelled]

    @property
    def complete(self):
        return (
            self.status in [ProgressStatus.healthy, ProgressStatus.completed]
            and self.percentage >= 100
        )

    @property
    def completed(self):
        return self.complete

    @property
    def failed(self):
        return self.status in [ProgressStatus.failed]

    @property
    def active(self):
        return self.status in [ProgressStatus.created, ProgressStatus.healthy]

    @property
    def inactive(self):
        return not self.active

    @property
    def ahead(self):
        import json

        import redis

        global BROKER

        from flask import current_app

        if self.celery_guid is None and self.sage_guid is None:
            return None

        if self.celery_guid:
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
                    if celery_guid:
                        celery_guid = uuid.UUID(celery_guid)
                        if celery_guid == self.celery_guid:
                            ahead = total - 1 - index
                            if ahead > 0:
                                return ahead
                except Exception:
                    pass

        if self.sage_guid:
            jobs = current_app.sage.request_passthrough_result(
                'engine.list', 'get', target='default'
            )['json_result']
            statuses, sage_jobs = current_app.sage.get_job_status(jobs, exclude_done=True)

            total = len(sage_jobs)
            for index, sage_job in enumerate(sage_jobs):
                sage_jobid, status = sage_job
                if sage_jobid == str(self.sage_guid):
                    ahead = total - 1 - index
                    if ahead > 0:
                        return ahead

        return 0

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'description=\'{self.description}\', '
            'status={self.status}, '
            'percentage={self.percentage}, '
            'eta={self.eta}, '
            'active={self.active}, '
            'complete={self.complete}, '
            'skipped={self.skipped}, '
            'failed={self.failed}, '
            'skipped={self.skipped}, '
            'created={self.created}, '
            'updated={self.updated}'
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def __iter__(self):
        assert (
            self.items and self.pgeta
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

    def skip(self, message=None):
        db.session.refresh(self)
        if self.status not in [ProgressStatus.created, ProgressStatus.healthy]:
            return
        with db.session.begin(subtransactions=True):
            self.status = ProgressStatus.skipped
            self.message = message
            db.session.merge(self)
        db.session.refresh(self)
        if self.parent:
            self.parent.notify(self.guid)

    def fail(self, message=None, chain=None):
        db.session.refresh(self)
        if self.status not in [ProgressStatus.created, ProgressStatus.healthy]:
            return
        with db.session.begin(subtransactions=True):
            self.status = ProgressStatus.failed
            self.message = message
            db.session.merge(self)
        db.session.refresh(self)
        if self.parent:
            self.parent.notify(self.guid, chain=chain)

    def cancel(self, message=None, chain=None):
        db.session.refresh(self)
        if self.status not in [ProgressStatus.created, ProgressStatus.healthy]:
            return
        with db.session.begin(subtransactions=True):
            self.status = ProgressStatus.cancelled
            self.message = message
            db.session.merge(self)
        db.session.refresh(self)
        if self.parent:
            self.parent.notify(self.guid, chain=chain)

    def delete(self, chain=None):
        parent = self.parent
        guid = self.guid
        with db.session.begin(subtransactions=True):
            db.session.delete(self)
        if parent:
            parent.notify(guid, chain=chain)

    def notify(self, step_guid, chain=None):
        if chain is None:
            chain = [step_guid]

        if self.guid in chain:
            # Make sure that we have not seen outselves already in the parent chain (loop)
            return

        chain.append(self.guid)

        steps = len(self.steps)
        if steps == 0:
            items = None
        else:
            items = list(range(1, steps + 1))

        if self.items is None or self.pgeta is None:
            self.config(items)
        elif steps and self.pgeta.denominator != steps:
            self.config(items)

        step = Progress.query.get(step_guid)

        if not step:
            # The step was deleted
            return

        try:
            if step.skipped:
                self.iterate(chain=chain)
            elif step.cancelled:
                self.iterate(chain=chain)
            elif step.completed:
                self.iterate(chain=chain)
            elif step.failed:
                message = 'Step {!r} failure: {!r}'.format(
                    step,
                    step.message,
                )
                self.fail(message, chain=chain)
            else:
                # The update was a step set progress percentage notification
                # Currently, do nothing because we only want to track steps that are complete
                pass
        except Exception:
            log.warning(
                'Failed to notify parent %r from step %r'
                % (
                    self,
                    step,
                )
            )

    def config(self, items=None):
        if items is None:
            steps = 100
            items = list(range(1, steps + 1))

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

    def iterate(self, amount=1, chain=None):
        self.pgeta.numerator += amount
        self.set(100.0 * self.pgeta.numerator / len(self.items), chain=chain)

    def increment(self, amount=1, chain=None):
        self.set(self.percentage + amount, chain=chain)

    def set(self, value, items=None, force=False, chain=None):
        new_percentage = int(max(0, min(100, value)))

        db.session.refresh(self)

        if self.status not in [
            ProgressStatus.created,
            ProgressStatus.healthy,
            ProgressStatus.skipped,
            ProgressStatus.cancelled,
        ]:
            # log.debug(
            #     'Attempting to set Progress %r to %d, but status is %r'
            #     % (
            #         self.guid,
            #         new_percentage,
            #         self.status,
            #     )
            # )
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
        if self.parent:
            self.parent.notify(self.guid, chain=chain)

        log.info('Updated {!r}'.format(self))

        return 'set'
