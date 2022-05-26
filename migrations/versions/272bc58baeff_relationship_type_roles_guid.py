# -*- coding: utf-8 -*-
"""empty message

Revision ID: 272bc58baeff
Revises: 9a6d8b560a5a
Create Date: 2022-04-12 15:51:41.958648

"""
import json
import uuid

import sqlalchemy as sa
from alembic import op

import app
import app.extensions

# revision identifiers, used by Alembic.
revision = '272bc58baeff'
down_revision = '9a6d8b560a5a'


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    conn = op.get_bind()
    relationship_type_roles = conn.execute(
        """
    SELECT data
    FROM site_setting
    WHERE key = 'relationship_type_roles'
    """
    ).first()
    if relationship_type_roles:
        relationship_type_roles = json.loads(relationship_type_roles.data)
    else:
        relationship_type_roles = {}

    # e.g. [('Family', ['Mother', 'Daughter'])]
    relationship_types = conn.execute(
        """
    SELECT relationship.type, array_agg(relationship_individual_member.individual_role)
    FROM relationship JOIN relationship_individual_member ON relationship.guid = relationship_individual_member.relationship_guid
    GROUP BY relationship.type
    """
    ).fetchall()
    relationship_types = dict(relationship_types)

    # Add new roles to existing relationship types
    for type_guid, type_def in relationship_type_roles.items():
        if type_def.get('label') in relationship_types:
            roles = relationship_types.pop(type_def['label'])
            roles_labels = [
                r.get('label') for r in type_def.get('roles', []) if 'label' in r
            ]
            for role in roles:
                if role not in roles_labels:
                    type_def.setdefault('roles', []).append(
                        {
                            'guid': str(uuid.uuid4()),
                            'label': role,
                        }
                    )

    # Create relationship types that don't exist
    for type_, roles in relationship_types.items():
        type_guid = str(uuid.uuid4())
        relationship_type_roles[type_guid] = {
            'guid': type_guid,
            'label': type_,
            'roles': [{'guid': str(uuid.uuid4()), 'label': role} for role in roles],
        }

    # Update site setting
    conn.execute(
        sa.sql.text(
            """
    UPDATE site_setting
    SET data = :data
    WHERE key = 'relationship_type_roles'
    """
        ),
        {'data': json.dumps(json.dumps(relationship_type_roles))},
    )
    # ^ Doing json.dumps twice to be consistent with the current broken
    # json storage, for example, we are storing an empty dict as '"{}"'

    with op.batch_alter_table('relationship', schema=None) as batch_op:
        batch_op.add_column(sa.Column('type_guid', app.extensions.GUID(), nullable=True))

    with op.batch_alter_table('relationship_individual_member', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('individual_role_guid', app.extensions.GUID(), nullable=True)
        )

    # Change relationship.type and individual_role to use guids
    for type_guid, type_def in relationship_type_roles.items():
        type_label = type_def.get('label')
        conn.execute(
            sa.sql.text(
                """
        UPDATE relationship
        SET type_guid = :type_guid
        WHERE type = :type
        """
            ),
            {'type_guid': type_guid, 'type': type_label},
        )
        for role in type_def.get('roles', []):
            conn.execute(
                sa.sql.text(
                    """
            UPDATE relationship_individual_member
            SET individual_role_guid = :individual_role_guid
            WHERE individual_role = :individual_role
            AND relationship_guid IN (
              SELECT guid
              FROM relationship
              WHERE type = :type)
            """
                ),
                {
                    'individual_role_guid': role.get('guid'),
                    'individual_role': role.get('label'),
                    'type': type_label,
                },
            )

    with op.batch_alter_table('relationship', schema=None) as batch_op:
        batch_op.drop_column('type')

    with op.batch_alter_table('relationship_individual_member', schema=None) as batch_op:
        batch_op.alter_column('individual_role_guid', nullable=False)
        batch_op.drop_column('individual_role')


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    conn = op.get_bind()
    relationship_type_roles = conn.execute(
        """
    SELECT data
    FROM site_setting
    WHERE key = 'relationship_type_roles'
    """
    ).first()
    if relationship_type_roles:
        relationship_type_roles = json.loads(relationship_type_roles.data)
    else:
        relationship_type_roles = {}

    with op.batch_alter_table('relationship_individual_member', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('individual_role', sa.VARCHAR(), autoincrement=False, nullable=True)
        )

    with op.batch_alter_table('relationship', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('type', sa.VARCHAR(), autoincrement=False, nullable=True)
        )

    # Populate individual_role and relationship.type
    for type_guid, type_def in relationship_type_roles.items():
        type_label = type_def.get('label')
        conn.execute(
            sa.sql.text(
                """
        UPDATE relationship
        SET type = :type
        WHERE type_guid = :type_guid
        """
            ),
            {'type': type_label, 'type_guid': type_guid},
        )
        for role in type_def.get('roles', []):
            conn.execute(
                sa.sql.text(
                    """
            UPDATE relationship_individual_member
            SET individual_role = :individual_role
            WHERE individual_role_guid = :individual_role_guid
            AND relationship_guid IN (
              SELECT guid
              FROM relationship
              WHERE type_guid = :type_guid)
            """
                ),
                {
                    'individual_role': role.get('label'),
                    'individual_role_guid': role.get('guid'),
                    'type_guid': type_guid,
                },
            )

    with op.batch_alter_table('relationship_individual_member', schema=None) as batch_op:
        batch_op.alter_column('individual_role', nullable=False)
        batch_op.drop_column('individual_role_guid')

    with op.batch_alter_table('relationship', schema=None) as batch_op:
        batch_op.drop_column('type_guid')

    # ### end Alembic commands ###
