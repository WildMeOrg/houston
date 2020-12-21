"""empty message

Revision ID: d7e0afc92ce2
Revises: 11cd9b6d0564
Create Date: 2020-12-18 13:30:16.667517

"""

# revision identifiers, used by Alembic.
revision = 'd7e0afc92ce2'
down_revision = '11cd9b6d0564'

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils

import app
import app.extensions



def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('project',
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('updated', sa.DateTime(), nullable=False),
    sa.Column('guid', app.extensions.GUID(), nullable=False),
    sa.Column('title', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('guid', name=op.f('pk_project'))
    )
    op.create_table('project_user_membership_enrollment',
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('updated', sa.DateTime(), nullable=False),
    sa.Column('viewed', sa.DateTime(), nullable=False),
    sa.Column('project_guid', app.extensions.GUID(), nullable=False),
    sa.Column('user_guid', app.extensions.GUID(), nullable=False),
    sa.ForeignKeyConstraint(['project_guid'], ['project.guid'], name=op.f('fk_project_user_membership_enrollment_project_guid_project')),
    sa.ForeignKeyConstraint(['user_guid'], ['user.guid'], name=op.f('fk_project_user_membership_enrollment_user_guid_user')),
    sa.PrimaryKeyConstraint('project_guid', 'user_guid', name=op.f('pk_project_user_membership_enrollment'))
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('project_user_membership_enrollment')
    op.drop_table('project')
    # ### end Alembic commands ###
