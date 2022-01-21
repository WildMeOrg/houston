"""empty message

Revision ID: 804d984e9dd4
Revises: 52af6deb082b
Create Date: 2022-01-19 00:38:15.978803

"""

# revision identifiers, used by Alembic.
revision = '804d984e9dd4'
down_revision = '52af6deb082b'

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
    with op.batch_alter_table('relationship', schema=None) as batch_op:
        batch_op.add_column(sa.Column('viewed', sa.DateTime(), nullable=False))
        batch_op.create_index(batch_op.f('ix_relationship_created'), ['created'], unique=False)
        batch_op.create_index(batch_op.f('ix_relationship_updated'), ['updated'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('relationship', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_relationship_updated'))
        batch_op.drop_index(batch_op.f('ix_relationship_created'))
        batch_op.drop_column('viewed')

    # ### end Alembic commands ###