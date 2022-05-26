# -*- coding: utf-8 -*-
"""empty message

Revision ID: adb5d1a314bc
Revises: fa952f537929
Create Date: 2021-06-03 23:26:29.091559

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'adb5d1a314bc'
down_revision = 'fa952f537929'


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('annotation', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'ia_class',
                sa.String(length=255),
                nullable=False,
                server_default='unknown',
            )
        )
        batch_op.add_column(
            sa.Column('bounds', sa.JSON(), nullable=False, server_default='{}')
        )
        batch_op.alter_column('ia_class', server_default=None)
        batch_op.alter_column('bounds', server_default=None)

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('annotation', schema=None) as batch_op:
        batch_op.drop_column('bounds')
        batch_op.drop_column('ia_class')

    # ### end Alembic commands ###
