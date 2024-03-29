# -*- coding: utf-8 -*-
"""empty message

Revision ID: 8083ed5f8d4f
Revises: 66bbd28297d2
Create Date: 2023-06-16 21:03:20.244828

"""
import sqlalchemy as sa
from alembic import op

import app
import app.extensions

# revision identifiers, used by Alembic.
revision = '8083ed5f8d4f'
down_revision = '66bbd28297d2'


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'account_request',
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.Column('updated', sa.DateTime(), nullable=False),
        sa.Column('indexed', sa.DateTime(), nullable=False),
        sa.Column('viewed', sa.DateTime(), nullable=False),
        sa.Column('guid', app.extensions.GUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('message', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('guid', name=op.f('pk_account_request')),
    )
    with op.batch_alter_table('account_request', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_account_request_created'), ['created'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_account_request_email'), ['email'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_account_request_indexed'), ['indexed'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_account_request_name'), ['name'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_account_request_updated'), ['updated'], unique=False
        )

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('account_request', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_account_request_updated'))
        batch_op.drop_index(batch_op.f('ix_account_request_name'))
        batch_op.drop_index(batch_op.f('ix_account_request_indexed'))
        batch_op.drop_index(batch_op.f('ix_account_request_email'))
        batch_op.drop_index(batch_op.f('ix_account_request_created'))

    op.drop_table('account_request')
    # ### end Alembic commands ###
