# -*- coding: utf-8 -*-
"""empty message

Revision ID: fd467d5e0812
Revises: 19dd4e2c1e63
Create Date: 2022-04-06 10:25:46.398750

"""
import sqlalchemy as sa
from alembic import op

import app
import app.extensions

# revision identifiers, used by Alembic.
revision = 'fd467d5e0812'
down_revision = '19dd4e2c1e63'


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('asset_group_sighting', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'detection_attempts', sa.Integer(), nullable=False, server_default='0'
            )
        )
        batch_op.alter_column('detection_attempts', server_default='0')

    with op.batch_alter_table('sighting', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('job_configs', app.extensions.JSON(), nullable=True)
        )

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('sighting', schema=None) as batch_op:
        batch_op.drop_column('job_configs')

    with op.batch_alter_table('asset_group_sighting', schema=None) as batch_op:
        batch_op.drop_column('detection_attempts')

    # ### end Alembic commands ###
