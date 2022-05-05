# -*- coding: utf-8 -*-
"""empty message

Revision ID: 32ff72c42c26
Revises: cc1f915cde87
Create Date: 2022-05-05 20:56:49.245636

"""
from alembic import op
import sqlalchemy as sa

import app
import app.extensions


# revision identifiers, used by Alembic.
revision = '32ff72c42c26'
down_revision = 'cc1f915cde87'


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('asset_group', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('progress_preparation_guid', app.extensions.GUID(), nullable=True)
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_asset_group_progress_preparation_guid_progress'),
            'progress',
            ['progress_preparation_guid'],
            ['guid'],
        )

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('asset_group', schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_asset_group_progress_preparation_guid_progress'),
            type_='foreignkey',
        )
        batch_op.drop_column('progress_preparation_guid')

    # ### end Alembic commands ###
