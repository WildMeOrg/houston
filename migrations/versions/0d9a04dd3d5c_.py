# -*- coding: utf-8 -*-
"""empty message

Revision ID: 0d9a04dd3d5c
Revises: 4b70e9af2070
Create Date: 2023-07-24 22:54:08.371879

"""
import sqlalchemy as sa

# import sqlalchemy_utils
from alembic import op

# import app
# import app.extensions

# revision identifiers, used by Alembic.
revision = '0d9a04dd3d5c'
down_revision = '4b70e9af2070'


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('autogenerated_name', schema=None) as batch_op:
        batch_op.add_column(sa.Column('enabled', sa.Boolean(), nullable=False))

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('autogenerated_name', schema=None) as batch_op:
        batch_op.drop_column('enabled')

    # ### end Alembic commands ###
