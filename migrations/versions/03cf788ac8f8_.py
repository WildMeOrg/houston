# -*- coding: utf-8 -*-
"""empty message

Revision ID: 03cf788ac8f8
Revises: 634551347a44
Create Date: 2022-03-15 15:24:12.242789

"""
from alembic import op
import sqlalchemy as sa

import app
import app.extensions


# revision identifiers, used by Alembic.
revision = '03cf788ac8f8'
down_revision = '634551347a44'


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'integrity',
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.Column('updated', sa.DateTime(), nullable=False),
        sa.Column('viewed', sa.DateTime(), nullable=False),
        sa.Column('guid', app.extensions.GUID(), nullable=False),
        sa.Column('result', app.extensions.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('guid', name=op.f('pk_integrity')),
    )
    with op.batch_alter_table('integrity', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_integrity_created'), ['created'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_integrity_updated'), ['updated'], unique=False
        )

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('integrity', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_integrity_updated'))
        batch_op.drop_index(batch_op.f('ix_integrity_created'))

    op.drop_table('integrity')
    # ### end Alembic commands ###
