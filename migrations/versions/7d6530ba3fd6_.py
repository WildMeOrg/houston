"""empty message

Revision ID: 7d6530ba3fd6
Revises: a042326c4b51
Create Date: 2020-10-09 12:09:06.882462

"""

# revision identifiers, used by Alembic.
revision = '7d6530ba3fd6'
down_revision = 'a042326c4b51'

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils

import app
import app.extensions



def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('asset', schema=None) as batch_op:
        batch_op.add_column(sa.Column('content_guid', app.extensions.GUID(), nullable=True))
        batch_op.add_column(sa.Column('filesystem_guid', app.extensions.GUID(), nullable=False))
        batch_op.add_column(sa.Column('semantic_guid', app.extensions.GUID(), nullable=False))
        batch_op.add_column(sa.Column('size_bytes', sa.BigInteger(), nullable=True))
        batch_op.create_unique_constraint(batch_op.f('uq_asset_semantic_guid'), ['semantic_guid'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('asset', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('uq_asset_semantic_guid'), type_='unique')
        batch_op.drop_column('size_bytes')
        batch_op.drop_column('semantic_guid')
        batch_op.drop_column('filesystem_guid')
        batch_op.drop_column('content_guid')

    # ### end Alembic commands ###
