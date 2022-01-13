# -*- coding: utf-8 -*-
"""
Missions database models
--------------------
"""
import uuid

from app.extensions import db, HoustonModel, Timestamp
from flask import current_app
import logging

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class MissionUserAssignment(db.Model, HoustonModel):

    mission_guid = db.Column(db.GUID, db.ForeignKey('mission.guid'), primary_key=True)

    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), primary_key=True)

    mission = db.relationship('Mission', back_populates='user_assignments')

    user = db.relationship('User', backref=db.backref('mission_assignments'))


class MissionAssetParticipation(db.Model, HoustonModel):

    mission_guid = db.Column(db.GUID, db.ForeignKey('mission.guid'), primary_key=True)

    asset_guid = db.Column(db.GUID, db.ForeignKey('asset.guid'), primary_key=True)

    mission = db.relationship('Mission', back_populates='asset_participations')

    asset = db.relationship('Asset', backref=db.backref('mission_participations'))


class Mission(db.Model, HoustonModel, Timestamp):
    """
    Missions database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    title = db.Column(db.String(length=50), nullable=False)

    owner_guid = db.Column(
        db.GUID, db.ForeignKey('user.guid'), index=True, nullable=False
    )
    # owner = db.relationship('User', back_populates='owned_missions')
    owner = db.relationship(
        'User',
        backref=db.backref(
            'owned_missions',
            primaryjoin='User.guid == Mission.owner_guid',
            order_by='Mission.guid',
        ),
    )

    user_assignments = db.relationship('MissionUserAssignment', back_populates='mission')

    asset_participations = db.relationship(
        'MissionAssetParticipation', back_populates='mission'
    )

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
        participation = MissionAssetParticipation(
            mission=self,
            asset=asset,
        )

        db.session.add(participation)
        self.asset_participations.append(participation)

    def remove_asset_in_context(self, asset):
        for participation in self.asset_participations:
            if participation.asset == asset:
                db.session.delete(participation)
                break

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

    def delete(self):
        with db.session.begin():
            while self.user_assignments:
                db.session.delete(self.user_assignments.pop())
            db.session.delete(self)
            while self.asset_participations:
                db.session.delete(self.asset_participations.pop())
            db.session.delete(self)
