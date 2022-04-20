# -*- coding: utf-8 -*-
"""
Relationships database models
--------------------
"""

from app.extensions import HoustonModel, db
from datetime import datetime  # NOQA
import app.extensions.logging as AuditLog

import uuid

import logging

log = logging.getLogger(__name__)


class RelationshipIndividualMember(db.Model, HoustonModel):

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    relationship_guid = db.Column(db.GUID, db.ForeignKey('relationship.guid'))
    relationship = db.relationship(
        'Relationship', backref=db.backref('individual_members')
    )

    individual_guid = db.Column(db.GUID, db.ForeignKey('individual.guid'))
    individual = db.relationship(
        'Individual', backref=db.backref('relationship_memberships')
    )

    individual_role_guid = db.Column(db.GUID, nullable=False)

    def __init__(self, individual, individual_role_guid, type_guid=None, **kwargs):
        self.individual = individual
        self.individual_role_guid = individual_role_guid
        self.individual_guid = individual.guid

        from app.modules.site_settings.models import SiteSetting

        relationship_type_roles = SiteSetting.get_value(
            'relationship_type_roles', {}
        ).values()

        valid_role_guids = []
        for relationship_type in relationship_type_roles:
            if type_guid is None or relationship_type.get('guid') == type_guid:
                for role in relationship_type.get('roles', []):
                    if role.get('guid'):
                        valid_role_guids.append(role['guid'])

        if individual_role_guid not in valid_role_guids:
            raise ValueError(
                f'Role guid "{individual_role_guid}" not found in site setting "relationship_type_roles" for relationship type guid "{type_guid}"'
            )

    @property
    def individual_first_name(self):
        from app.modules.names.models import Name

        first_name = Name.query.filter_by(
            individual=self.individual, context='FirstName'
        ).first()
        if first_name:
            return first_name.value

    @property
    def individual_role_label(self):
        from app.modules.site_settings.models import SiteSetting

        relationship_type_roles = SiteSetting.get_value(
            'relationship_type_roles', {}
        ).values()

        for relationship_type in relationship_type_roles:
            for role in relationship_type.get('roles', []):
                if role.get('guid') == str(self.individual_role_guid):
                    return role.get('label')

    def delete(self):
        relationship = Relationship.query.get(self.relationship_guid)
        relationship.delete()


class Relationship(db.Model, HoustonModel):
    """
    Relationships database model.
    """

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name

    start_date = db.Column(
        db.DateTime, index=True, default=datetime.utcnow, nullable=True
    )
    end_date = db.Column(db.DateTime, index=True, default=datetime.utcnow, nullable=True)

    type_guid = db.Column(db.GUID, nullable=True)

    @classmethod
    def get_elasticsearch_schema(cls):
        from app.modules.relationships.schemas import DetailedRelationshipSchema

        return DetailedRelationshipSchema

    def __init__(
        self,
        individual_1_guid,
        individual_2_guid,
        individual_1_role_guid,
        individual_2_role_guid,
        type_guid=None,
        **kwargs,
    ):
        if (
            individual_1_guid
            and individual_2_guid
            and individual_1_role_guid
            and individual_2_role_guid
        ):

            from app.modules.individuals.models import Individual

            individual_1 = Individual.query.get(individual_1_guid)
            individual_2 = Individual.query.get(individual_2_guid)

            if individual_1 and individual_2:
                member_1 = RelationshipIndividualMember(
                    individual_1, individual_1_role_guid, type_guid=type_guid
                )
                member_2 = RelationshipIndividualMember(
                    individual_2, individual_2_role_guid, type_guid=type_guid
                )
                self.individual_members.append(member_1)
                self.individual_members.append(member_2)
            else:
                raise ValueError(
                    'One of the Individual guids used to attempt Relationship creation was invalid.'
                )
            self.type_guid = type_guid
        else:
            raise ValueError('Relationship needs two individuals, each with a role guid.')

    @property
    def type_label(self):
        from app.modules.site_settings.models import SiteSetting

        relationship_type_roles = SiteSetting.get_value(
            'relationship_type_roles', {}
        ).values()

        for relationship_type in relationship_type_roles:
            if relationship_type.get('guid') == str(self.type_guid):
                return relationship_type.get('label')

    def has_individual(self, individual_guid):
        if self._get_membership_for_guid(individual_guid):
            return True
        return False

    def get_relationship_role_for_individual(self, individual_guid):
        membership = self._get_membership_for_guid(individual_guid)
        if membership:
            for individual_member in self.individual_members:
                if individual_member.individual_guid == individual_guid:
                    return (
                        individual_member.individual_role_label,
                        individual_member.individual_role_guid,
                    )
        return None

    def _get_membership_for_guid(self, individual_guid):
        found_individual_members = [
            individual_member
            for individual_member in self.individual_members
            if individual_member.individual_guid == individual_guid
        ]
        if len(found_individual_members) == 0:
            return None
        return found_individual_members[0]

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, '
            'individual_member_1={self.individual_members[0].individual_guid}, '
            'individual_member_2={self.individual_members[1].individual_guid}, '
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def delete(self):
        AuditLog.delete_object(log, self)

        with db.session.begin(subtransactions=True):
            for individual_member in self.individual_members:
                db.session.delete(individual_member)
            db.session.delete(self)
