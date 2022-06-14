# -*- coding: utf-8 -*-
"""autogen_names

Revision ID: 2b6c5e9d34ab
Revises: 1cdb69cbdcaa
Create Date: 2022-06-15 14:45:59.708324

"""
import sqlalchemy as sa
from alembic import op

import app
import app.extensions

# revision identifiers, used by Alembic.
revision = '2b6c5e9d34ab'
down_revision = '1cdb69cbdcaa'


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """

    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'autogenerated_name',
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.Column('updated', sa.DateTime(), nullable=False),
        sa.Column('indexed', sa.DateTime(), nullable=False),
        sa.Column('viewed', sa.DateTime(), nullable=False),
        sa.Column('guid', app.extensions.GUID(), nullable=False),
        sa.Column(
            'type',
            sa.Enum(
                'species',
                'region',
                'project',
                'organization',
                name='autogeneratednametype',
            ),
            nullable=False,
        ),
        sa.Column('prefix', sa.String(), nullable=False),
        sa.Column('reference_guid', app.extensions.GUID(), nullable=True),
        sa.Column('next_value', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('guid', name=op.f('pk_autogenerated_name')),
    )
    with op.batch_alter_table('autogenerated_name', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_autogenerated_name_created'), ['created'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_autogenerated_name_indexed'), ['indexed'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_autogenerated_name_prefix'), ['prefix'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_autogenerated_name_reference_guid'),
            ['reference_guid'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_autogenerated_name_type'), ['type'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_autogenerated_name_updated'), ['updated'], unique=False
        )

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('autogenerated_name', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_autogenerated_name_updated'))
        batch_op.drop_index(batch_op.f('ix_autogenerated_name_type'))
        batch_op.drop_index(batch_op.f('ix_autogenerated_name_reference_guid'))
        batch_op.drop_index(batch_op.f('ix_autogenerated_name_prefix'))
        batch_op.drop_index(batch_op.f('ix_autogenerated_name_indexed'))
        batch_op.drop_index(batch_op.f('ix_autogenerated_name_created'))

    op.drop_table('autogenerated_name')

    # drop Enum created above
    sa.Enum(name='autogeneratednametype').drop(op.get_bind(), checkfirst=False)

    # ### end Alembic commands ###
