# -*- coding: utf-8 -*-
"""empty message

Revision ID: a7396fa56571
Revises: 58bf0e49cbf7
Create Date: 2021-06-28 16:52:08.158630

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a7396fa56571'
down_revision = '58bf0e49cbf7'


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('job_control')
    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'job_control',
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.Column('updated', sa.DateTime(), nullable=False),
        sa.Column('viewed', sa.DateTime(), nullable=False),
        sa.Column('guid', sa.CHAR(length=32), nullable=False),
        sa.Column('asset_group_sighting_uuid', sa.CHAR(length=32), nullable=True),
        sa.Column('annotation_uuid', sa.CHAR(length=32), nullable=True),
        sa.PrimaryKeyConstraint('guid', name='pk_job_control'),
    )
    # ### end Alembic commands ###
