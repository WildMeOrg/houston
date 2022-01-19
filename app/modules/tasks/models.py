# -*- coding: utf-8 -*-
"""
Tasks database models
--------------------
"""
import uuid
import enum

from app.extensions import db, HoustonModel, Timestamp


class TaskTypes(str, enum.Enum):
    placeholder = 'placeholder'


class TaskUserAssignment(db.Model, HoustonModel):

    task_guid = db.Column(db.GUID, db.ForeignKey('task.guid'), primary_key=True)

    user_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), primary_key=True)

    task = db.relationship('Task', back_populates='user_assignments')

    user = db.relationship(
        'User', backref=db.backref('task_assignments', cascade='delete, delete-orphan')
    )


class TaskAssetParticipation(db.Model, HoustonModel):

    task_guid = db.Column(db.GUID, db.ForeignKey('task.guid'), primary_key=True)

    asset_guid = db.Column(db.GUID, db.ForeignKey('asset.guid'), primary_key=True)

    task = db.relationship('Task', back_populates='asset_participations')

    asset = db.relationship(
        'Asset',
        backref=db.backref('task_participations', cascade='delete, delete-orphan'),
    )


class TaskAnnotationParticipation(db.Model, HoustonModel):

    task_guid = db.Column(db.GUID, db.ForeignKey('task.guid'), primary_key=True)

    annotation_guid = db.Column(
        db.GUID, db.ForeignKey('annotation.guid'), primary_key=True
    )

    task = db.relationship('Task', back_populates='annotation_participations')

    annotation = db.relationship(
        'Annotation',
        backref=db.backref('task_participations', cascade='delete, delete-orphan'),
    )


class Task(db.Model, HoustonModel, Timestamp):
    """
    Tasks database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    title = db.Column(db.String(length=50), nullable=False)

    type = db.Column(db.Enum(TaskTypes), default=TaskTypes.placeholder, nullable=False)

    owner_guid = db.Column(db.GUID, db.ForeignKey('user.guid'), index=True, nullable=True)
    owner = db.relationship(
        'User',
        backref=db.backref(
            'owned_tasks',
            primaryjoin='User.guid == Task.owner_guid',
            order_by='Task.guid',
        ),
    )

    mission_guid = db.Column(
        db.GUID, db.ForeignKey('mission.guid'), index=True, nullable=True
    )
    mission = db.relationship(
        'Mission',
        backref=db.backref(
            'tasks',
            primaryjoin='Mission.guid == Task.mission_guid',
            order_by='Task.guid',
        ),
    )

    user_assignments = db.relationship('TaskUserAssignment', back_populates='task')

    asset_participations = db.relationship(
        'TaskAssetParticipation', back_populates='task'
    )

    annotation_participations = db.relationship(
        'TaskAnnotationParticipation', back_populates='task'
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
        assignment = TaskUserAssignment(
            task=self,
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
        participation = TaskAssetParticipation(
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
        participation = TaskAssetParticipation(
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
