# -*- coding: utf-8 -*-
"""empty message

Revision ID: cccb5639bfd9
Revises: 214ba937eadf
Create Date: 2021-12-02 23:06:23.742054

"""
import sqlalchemy as sa
from alembic import op

import app
import app.extensions

# revision identifiers, used by Alembic.
revision = 'cccb5639bfd9'
down_revision = '214ba937eadf'


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'name',
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.Column('updated', sa.DateTime(), nullable=False),
        sa.Column('viewed', sa.DateTime(), nullable=False),
        sa.Column('guid', app.extensions.GUID(), nullable=False),
        sa.Column('value', sa.String(), nullable=False),
        sa.Column('context', sa.String(), nullable=False),
        sa.Column('individual_guid', app.extensions.GUID(), nullable=False),
        sa.Column('creator_guid', app.extensions.GUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ['creator_guid'], ['user.guid'], name=op.f('fk_name_creator_guid_user')
        ),
        sa.ForeignKeyConstraint(
            ['individual_guid'],
            ['individual.guid'],
            name=op.f('fk_name_individual_guid_individual'),
        ),
        sa.PrimaryKeyConstraint('guid', name=op.f('pk_name')),
        sa.UniqueConstraint('context', 'individual_guid', name=op.f('uq_name_context')),
    )
    with op.batch_alter_table('name', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_name_context'), ['context'], unique=False)
        batch_op.create_index(batch_op.f('ix_name_created'), ['created'], unique=False)
        batch_op.create_index(
            batch_op.f('ix_name_creator_guid'), ['creator_guid'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_name_individual_guid'), ['individual_guid'], unique=False
        )
        batch_op.create_index(batch_op.f('ix_name_updated'), ['updated'], unique=False)
        batch_op.create_index(batch_op.f('ix_name_value'), ['value'], unique=False)

    op.create_table(
        'name_preferring_users_join',
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.Column('updated', sa.DateTime(), nullable=False),
        sa.Column('viewed', sa.DateTime(), nullable=False),
        sa.Column('name_guid', app.extensions.GUID(), nullable=False),
        sa.Column('user_guid', app.extensions.GUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ['name_guid'],
            ['name.guid'],
            name=op.f('fk_name_preferring_users_join_name_guid_name'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_guid'],
            ['user.guid'],
            name=op.f('fk_name_preferring_users_join_user_guid_user'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint(
            'name_guid', 'user_guid', name=op.f('pk_name_preferring_users_join')
        ),
    )
    with op.batch_alter_table('name_preferring_users_join', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_name_preferring_users_join_created'), ['created'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_name_preferring_users_join_updated'), ['updated'], unique=False
        )

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('name_preferring_users_join', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_name_preferring_users_join_updated'))
        batch_op.drop_index(batch_op.f('ix_name_preferring_users_join_created'))

    op.drop_table('name_preferring_users_join')
    with op.batch_alter_table('name', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_name_value'))
        batch_op.drop_index(batch_op.f('ix_name_updated'))
        batch_op.drop_index(batch_op.f('ix_name_individual_guid'))
        batch_op.drop_index(batch_op.f('ix_name_creator_guid'))
        batch_op.drop_index(batch_op.f('ix_name_created'))
        batch_op.drop_index(batch_op.f('ix_name_context'))

    op.drop_table('name')
    # ### end Alembic commands ###
