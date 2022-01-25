# -*- coding: utf-8 -*-
"""
Missions database models
--------------------
"""
import uuid
import enum

from app.extensions import db, HoustonModel, Timestamp
from app.extensions.git_store import GitStore

from flask import current_app
import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class MissionUserAssignment(db.Model, HoustonModel):
    mission_guid = db.Column(db.GUID, db.ForeignKey('mission.guid'), primary_key=True)

    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), primary_key=True)

    mission = db.relationship('Mission', back_populates='user_assignments')

    user = db.relationship(
        'User', backref=db.backref('mission_assignments', cascade='delete, delete-orphan')
    )


class Mission(db.Model, HoustonModel, Timestamp):
    """
    Missions database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    title = db.Column(db.String(length=50), nullable=False, unique=True)

    owner_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True)
    owner = db.relationship(
        'User',
        backref=db.backref(
            'mission_ownerships',
            primaryjoin='User.guid == Mission.owner_guid',
            order_by='Mission.guid',
        ),
    )

    user_assignments = db.relationship('MissionUserAssignment', back_populates='mission')

    options = db.Column(db.JSON, default=lambda: {}, nullable=False)

    classifications = db.Column(db.JSON, nullable=True)

    notes = db.Column(db.UnicodeText, nullable=True)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            "title='{self.title}', "
            'members={members} '
            ')>'.format(
                class_name=self.__class__.__name__,
                self=self,
                members=self.get_assigned_users(),
            )
        )

    @db.validates('title')
    def validate_title(self, key, title):  # pylint: disable=unused-argument,no-self-use
        if len(title) < 3:
            raise ValueError('Title has to be at least 3 characters long.')
        return title

    @classmethod
    def query_search(cls, search=None):
        from sqlalchemy import or_, and_, String
        from sqlalchemy_utils.functions import cast_if

        if search is not None:
            search = search.strip().replace(',', ' ').split(' ')
            search = [term.strip() for term in search]
            search = [term for term in search if len(term) > 0]

            or_terms = []
            for term in search:
                or_term = or_(
                    cast_if(cls.guid, String).contains(term),
                    cls.title.contains(term),
                    cast_if(cls.owner_guid, String).contains(term),
                )
                or_terms.append(or_term)
            query = cls.query.filter(and_(*or_terms))
        else:
            query = cls.query

        return query

    def get_options(self):
        return self.options.get('model_options', [])

    def get_assigned_users(self):
        return [assignment.user for assignment in self.user_assignments]

    def get_members(self):
        return self.get_assigned_users()

    def add_user(self, user):
        with db.session.begin():
            self.add_user_in_context(user)

    def add_user_in_context(self, user):
        assignment = MissionUserAssignment(
            mission=self,
            user=user,
        )

        db.session.add(assignment)
        self.user_assignments.append(assignment)

    def user_is_owner(self, user):
        return user is not None and user == self.owner

    def remove_user_in_context(self, user):
        for assignment in self.user_assignments:
            if assignment.user == user:
                db.session.delete(assignment)
                break

    def get_assets(self):
        assets = []
        for collection in self.collections:
            assets += collection.assets
        return assets

    def get_jobs_json(self):
        job_data = []
        for job in self.jobs:
            from app.modules.missions.schemas import DetailedMissionJobSchema

            schema = DetailedMissionJobSchema()
            this_job = schema.dump(self.jobs[job]).data
            this_job['job_id'] = job
            job_data.append(this_job)

        return job_data

    @classmethod
    def check_jobs(cls):
        for mission in Mission.query.all():
            mission.check_all_job_status()

    def check_all_job_status(self):
        jobs = self.jobs
        if not jobs:
            return
        for job_id in jobs.keys():
            job = jobs[job_id]
            if job['active']:
                current_app.acm.request_passthrough_result(
                    'job.response', 'post', {}, job
                )

    @classmethod
    def print_jobs(cls):
        for mission in Mission.query.all():
            mission.print_active_jobs()

    def print_active_jobs(self):
        for job_id in self.jobs.keys():
            job = self.jobs[job_id]
            if job['active']:
                log.warning(
                    f'Mission:{self.guid} Job:{job_id}' f"UTC Start:{job['start']}"
                )

    def any_jobs_active(self):
        jobs = self.jobs
        if not jobs:
            return False
        for job_id in jobs.keys():
            job = jobs[job_id]
            if job['active']:
                return True
        return False

    def get_job_details(self):

        details = {}
        for job_id in self.jobs.keys():
            details[job_id] = self.jobs[job_id]

        return details

    def send_mws_backend_operation(self):
        from datetime import datetime

        model_options = self.get_options()
        job_uuid = uuid.uuid4()

        self.jobs[str(job_uuid)] = {
            'active': True,
            'start': datetime.utcnow(),
            'options': model_options,
        }
        self.jobs = self.jobs
        with db.session.begin(subtransactions=True):
            db.session.merge(self)

    def delete_cascade(self):
        with db.session.begin(subtransactions=True):
            while self.user_assignments:
                db.session.delete(self.user_assignments.pop())
            while self.collections:
                db.session.delete(self.collections.pop())
            db.session.delete(self)

    def delete(self):
        with db.session.begin():
            db.session.delete(self)


class MissionCollection(GitStore):
    """
    MissionCollection database model.
    """

    GIT_STORE_NAME = 'mission_collections'

    GIT_STORE_DATABASE_PATH_CONFIG_NAME = 'MISSION_COLLECTION_DATABASE_PATH'

    guid = db.Column(db.GUID, db.ForeignKey('git_store.guid'), primary_key=True)

    mission_guid = db.Column(
        db.GUID,
        db.ForeignKey('mission.guid'),
        index=True,
        nullable=False,
    )
    mission = db.relationship(
        'Mission',
        backref=db.backref('collections', cascade='delete, delete-orphan'),
    )

    __mapper_args__ = {
        'polymorphic_identity': 'mission_collection',
    }

    @classmethod
    def ensure_remote_delay(cls, mission_collection):
        from .tasks import ensure_remote

        ensure_remote.delay(str(mission_collection.guid))

    def git_push_delay(self):
        from .tasks import git_push

        git_push.delay(str(self.guid))

    def delete_remote_delay(self):
        from .tasks import delete_remote

        delete_remote.delay(str(self.guid))


class MissionTaskTypes(str, enum.Enum):
    placeholder = 'placeholder'


class MissionTaskUserAssignment(db.Model, HoustonModel):

    mission_task_guid = db.Column(
        db.GUID, db.ForeignKey('mission_task.guid'), primary_key=True
    )

    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), primary_key=True)

    mission_task = db.relationship('MissionTask', back_populates='user_assignments')

    user = db.relationship(
        'User',
        backref=db.backref('mission_task_assignments', cascade='delete, delete-orphan'),
    )


class MissionTaskAssetParticipation(db.Model, HoustonModel):

    mission_task_guid = db.Column(
        db.GUID, db.ForeignKey('mission_task.guid'), primary_key=True
    )

    asset_guid = db.Column(db.GUID, db.ForeignKey('asset.guid'), primary_key=True)

    mission_task = db.relationship('MissionTask', back_populates='asset_participations')

    asset = db.relationship(
        'Asset',
        backref=db.backref(
            'mission_task_participations', cascade='delete, delete-orphan'
        ),
    )


class MissionTaskAnnotationParticipation(db.Model, HoustonModel):

    mission_task_guid = db.Column(
        db.GUID, db.ForeignKey('mission_task.guid'), primary_key=True
    )

    annotation_guid = db.Column(
        db.GUID, db.ForeignKey('annotation.guid'), primary_key=True
    )

    mission_task = db.relationship(
        'MissionTask', back_populates='annotation_participations'
    )

    annotation = db.relationship(
        'Annotation',
        backref=db.backref(
            'mission_task_participations', cascade='delete, delete-orphan'
        ),
    )


class MissionTask(db.Model, HoustonModel, Timestamp):
    """
    MissionTasks database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    title = db.Column(db.String(length=50), nullable=False)

    type = db.Column(
        db.Enum(MissionTaskTypes), default=MissionTaskTypes.placeholder, nullable=False
    )

    owner_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True)
    owner = db.relationship(
        'User',
        backref=db.backref(
            'mission_task_ownerships',
            primaryjoin='User.guid == MissionTask.owner_guid',
            order_by='MissionTask.guid',
        ),
    )

    mission_guid = db.Column(
        db.GUID, db.ForeignKey('mission.guid'), index=True, nullable=True
    )
    mission = db.relationship(
        'Mission',
        backref=db.backref(
            'mission_tasks',
            primaryjoin='Mission.guid == MissionTask.mission_guid',
            order_by='MissionTask.guid',
        ),
    )

    user_assignments = db.relationship(
        'MissionTaskUserAssignment', back_populates='mission_task'
    )

    asset_participations = db.relationship(
        'MissionTaskAssetParticipation', back_populates='mission_task'
    )

    annotation_participations = db.relationship(
        'MissionTaskAnnotationParticipation', back_populates='mission_task'
    )

    notes = db.Column(db.UnicodeText, nullable=True)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            "title='{self.title}', "
            'members={members} '
            ')>'.format(
                class_name=self.__class__.__name__,
                self=self,
                members=self.get_assigned_users(),
            )
        )

    @db.validates('title')
    def validate_title(self, key, title):  # pylint: disable=unused-argument,no-self-use
        if len(title) < 3:
            raise ValueError('Title has to be at least 3 characters long.')
        return title

    def user_is_owner(self, user):
        return user is not None and user == self.owner

    def get_assigned_users(self):
        return [assignment.user for assignment in self.user_assignments]

    def get_members(self):
        return self.get_assigned_users()

    def add_user(self, user):
        with db.session.begin():
            self.add_user_in_context(user)

    def add_user_in_context(self, user):
        assignment = MissionTaskUserAssignment(
            mission_task=self,
            user=user,
        )

        db.session.add(assignment)
        self.user_assignments.append(assignment)

    def remove_user_in_context(self, user):
        for assignment in self.user_assignments:
            if assignment.user == user:
                db.session.delete(assignment)
                break

    def get_assets(self):
        return [participation.asset for participation in self.asset_participations]

    def add_asset(self, asset):
        with db.session.begin():
            self.add_asset_in_context(asset)

    def add_asset_in_context(self, asset):
        participation = MissionTaskAssetParticipation(
            task=self,
            asset=asset,
        )

        db.session.add(participation)
        self.asset_participations.append(participation)

    def remove_asset_in_context(self, asset):
        for participation in self.asset_participations:
            if participation.asset == asset:
                db.session.delete(participation)
                break

    def get_annotations(self):
        return [
            participation.annotation for participation in self.annotation_participations
        ]

    def add_annotation(self, annotation):
        with db.session.begin():
            self.add_annotation_in_context(annotation)

    def add_annotation_in_context(self, annotation):
        participation = MissionTaskAssetParticipation(
            task=self,
            annotation=annotation,
        )

        db.session.add(participation)
        self.annotation_participations.append(participation)

    def remove_annotation_in_context(self, annotation):
        for participation in self.annotation_participations:
            if participation.annotation == annotation:
                db.session.delete(participation)
                break

    def delete(self):
        with db.session.begin():
            while self.user_assignments:
                db.session.delete(self.user_assignments.pop())
            while self.asset_participations:
                db.session.delete(self.asset_participations.pop())
            while self.annotation_participations:
                db.session.delete(self.annotation_participations.pop())
            db.session.delete(self)
