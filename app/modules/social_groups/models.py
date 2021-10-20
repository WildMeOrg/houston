# -*- coding: utf-8 -*-
"""
Social Groups database models
--------------------
"""
import json
import logging

from app.extensions import db, HoustonModel
from app.utils import HoustonException
import app.extensions.logging as AuditLog

import uuid

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class SocialGroupIndividualMembership(db.Model, HoustonModel):

    group_guid = db.Column(db.GUID, db.ForeignKey('social_group.guid'), primary_key=True)

    individual_guid = db.Column(
        db.GUID, db.ForeignKey('individual.guid'), primary_key=True
    )
    role = db.Column(db.String, nullable=True)

    social_group = db.relationship(
        'SocialGroup', back_populates='members', order_by='SocialGroup.guid'
    )

    individual = db.relationship(
        'Individual', back_populates='social_groups', order_by='Individual.guid'
    )


class SocialGroup(db.Model, HoustonModel):
    """
    Social Groups database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    name = db.Column(db.String(length=50), nullable=False)

    members = db.relationship(
        'SocialGroupIndividualMembership',
        back_populates='social_group',
        order_by='SocialGroupIndividualMembership.group_guid',
    )

    def __init__(self, members, name):
        self.name = name
        from app.modules.individuals.models import Individual

        for member_guid in members:
            individual = Individual.query.get(member_guid)
            assert individual
            membership = SocialGroupIndividualMembership(
                social_group=self,
                individual=individual,
                role=members[member_guid].get('role'),
            )
            with db.session.begin(subtransactions=True):
                db.session.add(membership)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            "name='{self.name}'"
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    @classmethod
    def site_settings_updated(cls):
        from app.modules.site_settings.models import SiteSetting

        role_string = SiteSetting.get_string('social_group_roles')

        permitted_role_data = json.loads(role_string) if role_string else {}
        all_groups = SocialGroup.query.all()
        for group in all_groups:
            current_roles_singular = []
            for member in group.members:
                if not member.role:
                    continue
                if member.role not in permitted_role_data.keys():
                    # That role not supported anymore
                    msg = f"member {member.individual_guid} lost role {member.role} as it's no longer supported"
                    AuditLog.audit_log_object(log, group, msg)
                    member.role = None
                    continue

                # if a role is now only singular in the group and we have multiple, all we can do is audit it
                if permitted_role_data[member.role]['multipleInGroup']:
                    if current_roles_singular.get(member.role):
                        current_roles_singular[member.role] = False
                    else:
                        current_roles_singular[member.role] = False
            for role in current_roles_singular:
                if not current_roles_singular[role]:
                    msg = f"WARNING: multiple members with {role}. Can't guess which to remove"
                    AuditLog.audit_log_object(log, group, msg)

    @classmethod
    def validate_roles(cls, string_input):
        expected_fields = {'multipleInGroup'}
        json_data = json.loads(string_input)
        if not isinstance(json_data, dict):
            raise HoustonException(log, 'Role data needs to be a dictionary')
        for item in json_data:
            if not isinstance(json_data[item], dict):
                raise HoustonException(
                    log, 'Role data needs to be a dictionary of dictionaries'
                )

            if set(json_data[item].keys()) != set(expected_fields):
                raise HoustonException(
                    log,
                    f'Role dictionary must have the following keys : {expected_fields}',
                )

    def get_member_data_as_json(self):
        individual_data = {}
        for member in self.members:
            individual_data[str(member.individual_guid)] = {'role': member.role}

        return individual_data

    def delete(self):
        AuditLog.delete_object(log, self)

        with db.session.begin():
            for member in self.members:
                db.session.delete(member)
            db.session.delete(self)
