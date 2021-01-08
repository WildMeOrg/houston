"""empty message

Revision ID: daf15d36661f
Revises: d7e0afc92ce2
Create Date: 2021-01-08 16:28:50.893448

"""

# revision identifiers, used by Alembic.
revision = 'daf15d36661f'
down_revision = 'd7e0afc92ce2'

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
    op.create_table('sighting',
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('updated', sa.DateTime(), nullable=False),
    sa.Column('viewed', sa.DateTime(), nullable=False),
    sa.Column('guid', app.extensions.GUID(), nullable=False),
    sa.Column('title', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('guid', name=op.f('pk_sighting'))
    )
    op.create_table('project_encounter',
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('updated', sa.DateTime(), nullable=False),
    sa.Column('viewed', sa.DateTime(), nullable=False),
    sa.Column('project_guid', app.extensions.GUID(), nullable=False),
    sa.Column('encounter_guid', app.extensions.GUID(), nullable=False),
    sa.ForeignKeyConstraint(['encounter_guid'], ['encounter.guid'], name=op.f('fk_project_encounter_encounter_guid_encounter')),
    sa.ForeignKeyConstraint(['project_guid'], ['project.guid'], name=op.f('fk_project_encounter_project_guid_project')),
    sa.PrimaryKeyConstraint('project_guid', 'encounter_guid', name=op.f('pk_project_encounter'))
    )
    with op.batch_alter_table('encounter', schema=None) as batch_op:
        batch_op.add_column(sa.Column('owner_guid', app.extensions.GUID(), nullable=True))
        batch_op.add_column(sa.Column('public', sa.Boolean(), nullable=False))
        batch_op.add_column(sa.Column('sighting_guid', app.extensions.GUID(), nullable=True))
        batch_op.create_index(batch_op.f('ix_encounter_owner_guid'), ['owner_guid'], unique=False)
        batch_op.create_index(batch_op.f('ix_encounter_sighting_guid'), ['sighting_guid'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_encounter_sighting_guid_sighting'), 'sighting', ['sighting_guid'], ['guid'])
        batch_op.create_foreign_key(batch_op.f('fk_encounter_owner_guid_user'), 'user', ['owner_guid'], ['guid'])

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('encounter', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_encounter_owner_guid_user'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_encounter_sighting_guid_sighting'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_encounter_sighting_guid'))
        batch_op.drop_index(batch_op.f('ix_encounter_owner_guid'))
        batch_op.drop_column('sighting_guid')
        batch_op.drop_column('public')
        batch_op.drop_column('owner_guid')

    op.drop_table('project_encounter')
    op.drop_table('sighting')
    # ### end Alembic commands ###
