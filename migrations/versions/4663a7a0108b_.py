"""empty message

Revision ID: 4663a7a0108b
Revises: caf961b9ac34
Create Date: 2021-09-14 17:35:33.775558

"""

# revision identifiers, used by Alembic.
revision = '4663a7a0108b'
down_revision = 'caf961b9ac34'

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils

import app
import app.extensions



def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('collaboration', schema=None) as batch_op:
        batch_op.add_column(sa.Column('initiator_guid', app.extensions.GUID(), nullable=False))
        batch_op.add_column(sa.Column('edit_initiator_guid', app.extensions.GUID(), nullable=True))

    with op.batch_alter_table('collaboration_user_associations', schema=None) as batch_op:
        batch_op.drop_column('initiator')
        batch_op.drop_column('edit_initiator')

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('collaboration_user_associations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('edit_initiator', sa.BOOLEAN(), autoincrement=False, nullable=False))
        batch_op.add_column(sa.Column('initiator', sa.BOOLEAN(), autoincrement=False, nullable=False))

    with op.batch_alter_table('collaboration', schema=None) as batch_op:
        batch_op.drop_column('edit_initiator_guid')
        batch_op.drop_column('initiator_guid')

    # ### end Alembic commands ###
