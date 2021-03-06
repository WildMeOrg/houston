"""empty message

Revision ID: 06364a7a31be
Revises: 060344b8b804
Create Date: 2021-01-22 09:53:54.533585

"""

# revision identifiers, used by Alembic.
revision = '06364a7a31be'
down_revision = '060344b8b804'

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
    with op.batch_alter_table('project', schema=None) as batch_op:
        batch_op.add_column(sa.Column('owner_guid', app.extensions.GUID(), nullable=False))
        batch_op.create_index(batch_op.f('ix_project_owner_guid'), ['owner_guid'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_project_owner_guid_user'), 'user', ['owner_guid'], ['guid'])

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('project', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_project_owner_guid_user'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_project_owner_guid'))
        batch_op.drop_column('owner_guid')

    # ### end Alembic commands ###
