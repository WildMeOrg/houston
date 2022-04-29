# -*- coding: utf-8 -*-
"""Delete creator collaboration user associations and create audit logs

Revision ID: b58abf228d55
Revises: ed7b9eb99d21
Create Date: 2022-04-29 08:21:34.416039

"""
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b58abf228d55'
down_revision = 'ed7b9eb99d21'


def upgrade():
    """
    Upgrade Semantic Description:
        Delete creator collaboration user associations and create audit logs
    """
    conn = op.get_bind()
    # Find all the participants of collaborations created by someone else
    # that's not in the audit log
    collab_creators = conn.execute(
        """
        SELECT
          collaboration.guid,
          initiator.email,
          array_agg(ARRAY[u.guid::text, u.email, u.full_name]),
          collaboration.created
        FROM collaboration_user_associations cua
        JOIN collaboration ON cua.collaboration_guid = collaboration.guid
        JOIN "user" u ON cua.user_guid = u.guid
        JOIN "user" initiator ON collaboration.initiator_guid = initiator.guid
        WHERE
          -- All the old collaborations that has a creator
          collaboration.guid IN (
            SELECT collaboration_guid
            FROM collaboration_user_associations
            WHERE read_approval_state = 'creator'
             OR edit_approval_state = 'creator'
          )
          AND
          -- Find the participants
          (cua.read_approval_state != 'creator'
           OR cua.edit_approval_state != 'creator')
        GROUP BY
          collaboration.guid, collaboration.created, initiator.email
        """
    )
    # Some collaboration creations are already in the audit log, so skip those
    collab_guids_in_audit_log = [
        r[0]
        for r in conn.execute(
            """
            SELECT item_guid
            FROM audit_log
            WHERE module_name = 'Collaboration'
              AND audit_type = 'User Create'
            """
        )
    ]

    to_delete = []
    for collab_guid, initiator_email, users, collab_created in collab_creators:
        to_delete.append(collab_guid)
        if collab_guid in collab_guids_in_audit_log:
            continue
        users_strings = [
            f'<User(guid={user_guid}, email="{user_email}", name="{user_name}">'
            for (user_guid, user_email, user_name) in users
        ]
        conn.execute(
            sa.sql.text(
                """
                INSERT INTO audit_log (
                  created, updated, guid, module_name, item_guid,
                  audit_type, user_email, message
                )
                VALUES (
                  :created, :created, :guid, 'Collaboration', :collab_guid,
                  'User Create', :initiator_email, :message
                )
                """
            ),
            {
                'created': collab_created,
                'guid': uuid.uuid4(),
                'collab_guid': collab_guid,
                'initiator_email': initiator_email,
                'message': f'POST collaborations create collaboration between [{", ".join(users_strings)}]',
            },
        )

    if to_delete:
        conn.execute(
            sa.sql.text(
                """
                DELETE FROM collaboration_user_associations
                WHERE
                  collaboration_guid IN :to_delete
                  AND (
                    read_approval_state = 'creator'
                    OR edit_approval_state = 'creator'
                  )
                """
            ),
            {'to_delete': tuple(to_delete)},
        )


def downgrade():
    """
    Downgrade Semantic Description:
        NOOP
    """
    pass
