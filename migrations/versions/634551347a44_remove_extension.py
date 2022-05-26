# -*- coding: utf-8 -*-
"""remove_extension

Revision ID: 634551347a44
Revises: ea69d76faa6b
Create Date: 2022-03-11 10:17:08.567099

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '634551347a44'
down_revision = 'ea69d76faa6b'


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('asset', schema=None) as batch_op:
        batch_op.drop_index('ix_asset_extension')
        batch_op.drop_column('extension')

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('asset', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('extension', sa.VARCHAR(), autoincrement=False, nullable=False)
        )
        batch_op.create_index('ix_asset_extension', ['extension'], unique=False)

    # ### end Alembic commands ###
