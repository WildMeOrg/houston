"""empty message

Revision ID: 47a80ead3a90
Revises: 4aa284fa3f72
Create Date: 2022-01-11 23:41:19.450220

"""

# revision identifiers, used by Alembic.
revision = '47a80ead3a90'
down_revision = '4aa284fa3f72'

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
    op.create_table('mission_user_assignment',
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('updated', sa.DateTime(), nullable=False),
    sa.Column('viewed', sa.DateTime(), nullable=False),
    sa.Column('mission_guid', app.extensions.GUID(), nullable=False),
    sa.Column('user_guid', app.extensions.GUID(), nullable=False),
    sa.ForeignKeyConstraint(['mission_guid'], ['mission.guid'], name=op.f('fk_mission_user_assignment_mission_guid_mission')),
    sa.ForeignKeyConstraint(['user_guid'], ['user.guid'], name=op.f('fk_mission_user_assignment_user_guid_user')),
    sa.PrimaryKeyConstraint('mission_guid', 'user_guid', name=op.f('pk_mission_user_assignment'))
    )
    with op.batch_alter_table('mission_user_assignment', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_mission_user_assignment_created'), ['created'], unique=False)
        batch_op.create_index(batch_op.f('ix_mission_user_assignment_updated'), ['updated'], unique=False)

    op.create_table('task',
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('updated', sa.DateTime(), nullable=False),
    sa.Column('viewed', sa.DateTime(), nullable=False),
    sa.Column('guid', app.extensions.GUID(), nullable=False),
    sa.Column('title', sa.String(length=50), nullable=False),
    sa.Column('type', sa.Enum('placeholder', name='tasktypes'), nullable=False),
    sa.Column('owner_guid', app.extensions.GUID(), nullable=True),
    sa.Column('mission_guid', app.extensions.GUID(), nullable=True),
    sa.Column('notes', sa.UnicodeText(), nullable=True),
    sa.ForeignKeyConstraint(['mission_guid'], ['mission.guid'], name=op.f('fk_task_mission_guid_mission')),
    sa.ForeignKeyConstraint(['owner_guid'], ['user.guid'], name=op.f('fk_task_owner_guid_user')),
    sa.PrimaryKeyConstraint('guid', name=op.f('pk_task'))
    )
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_task_created'), ['created'], unique=False)
        batch_op.create_index(batch_op.f('ix_task_mission_guid'), ['mission_guid'], unique=False)
        batch_op.create_index(batch_op.f('ix_task_owner_guid'), ['owner_guid'], unique=False)
        batch_op.create_index(batch_op.f('ix_task_updated'), ['updated'], unique=False)

    op.create_table('asset_tags',
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('updated', sa.DateTime(), nullable=False),
    sa.Column('viewed', sa.DateTime(), nullable=False),
    sa.Column('asset_guid', app.extensions.GUID(), nullable=False),
    sa.Column('tag_guid', app.extensions.GUID(), nullable=False),
    sa.ForeignKeyConstraint(['asset_guid'], ['asset.guid'], name=op.f('fk_asset_tags_asset_guid_asset')),
    sa.ForeignKeyConstraint(['tag_guid'], ['keyword.guid'], name=op.f('fk_asset_tags_tag_guid_keyword')),
    sa.PrimaryKeyConstraint('asset_guid', 'tag_guid', name=op.f('pk_asset_tags'))
    )
    with op.batch_alter_table('asset_tags', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_asset_tags_created'), ['created'], unique=False)
        batch_op.create_index(batch_op.f('ix_asset_tags_updated'), ['updated'], unique=False)

    op.create_table('mission_asset_participation',
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('updated', sa.DateTime(), nullable=False),
    sa.Column('viewed', sa.DateTime(), nullable=False),
    sa.Column('mission_guid', app.extensions.GUID(), nullable=False),
    sa.Column('asset_guid', app.extensions.GUID(), nullable=False),
    sa.ForeignKeyConstraint(['asset_guid'], ['asset.guid'], name=op.f('fk_mission_asset_participation_asset_guid_asset')),
    sa.ForeignKeyConstraint(['mission_guid'], ['mission.guid'], name=op.f('fk_mission_asset_participation_mission_guid_mission')),
    sa.PrimaryKeyConstraint('mission_guid', 'asset_guid', name=op.f('pk_mission_asset_participation'))
    )
    with op.batch_alter_table('mission_asset_participation', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_mission_asset_participation_created'), ['created'], unique=False)
        batch_op.create_index(batch_op.f('ix_mission_asset_participation_updated'), ['updated'], unique=False)

    op.create_table('task_asset_participation',
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('updated', sa.DateTime(), nullable=False),
    sa.Column('viewed', sa.DateTime(), nullable=False),
    sa.Column('task_guid', app.extensions.GUID(), nullable=False),
    sa.Column('asset_guid', app.extensions.GUID(), nullable=False),
    sa.ForeignKeyConstraint(['asset_guid'], ['asset.guid'], name=op.f('fk_task_asset_participation_asset_guid_asset')),
    sa.ForeignKeyConstraint(['task_guid'], ['task.guid'], name=op.f('fk_task_asset_participation_task_guid_task')),
    sa.PrimaryKeyConstraint('task_guid', 'asset_guid', name=op.f('pk_task_asset_participation'))
    )
    with op.batch_alter_table('task_asset_participation', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_task_asset_participation_created'), ['created'], unique=False)
        batch_op.create_index(batch_op.f('ix_task_asset_participation_updated'), ['updated'], unique=False)

    op.create_table('task_user_assignment',
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('updated', sa.DateTime(), nullable=False),
    sa.Column('viewed', sa.DateTime(), nullable=False),
    sa.Column('task_guid', app.extensions.GUID(), nullable=False),
    sa.Column('user_guid', app.extensions.GUID(), nullable=False),
    sa.ForeignKeyConstraint(['task_guid'], ['task.guid'], name=op.f('fk_task_user_assignment_task_guid_task')),
    sa.ForeignKeyConstraint(['user_guid'], ['user.guid'], name=op.f('fk_task_user_assignment_user_guid_user')),
    sa.PrimaryKeyConstraint('task_guid', 'user_guid', name=op.f('pk_task_user_assignment'))
    )
    with op.batch_alter_table('task_user_assignment', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_task_user_assignment_created'), ['created'], unique=False)
        batch_op.create_index(batch_op.f('ix_task_user_assignment_updated'), ['updated'], unique=False)

    op.create_table('task_annotation_participation',
    sa.Column('created', sa.DateTime(), nullable=False),
    sa.Column('updated', sa.DateTime(), nullable=False),
    sa.Column('viewed', sa.DateTime(), nullable=False),
    sa.Column('task_guid', app.extensions.GUID(), nullable=False),
    sa.Column('annotation_guid', app.extensions.GUID(), nullable=False),
    sa.ForeignKeyConstraint(['annotation_guid'], ['annotation.guid'], name=op.f('fk_task_annotation_participation_annotation_guid_annotation')),
    sa.ForeignKeyConstraint(['task_guid'], ['task.guid'], name=op.f('fk_task_annotation_participation_task_guid_task')),
    sa.PrimaryKeyConstraint('task_guid', 'annotation_guid', name=op.f('pk_task_annotation_participation'))
    )
    with op.batch_alter_table('task_annotation_participation', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_task_annotation_participation_created'), ['created'], unique=False)
        batch_op.create_index(batch_op.f('ix_task_annotation_participation_updated'), ['updated'], unique=False)

    with op.batch_alter_table('mission_user_membership_enrollment', schema=None) as batch_op:
        batch_op.drop_index('ix_mission_user_membership_enrollment_created')
        batch_op.drop_index('ix_mission_user_membership_enrollment_updated')

    op.drop_table('mission_user_membership_enrollment')
    with op.batch_alter_table('annotation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contributor_guid', app.extensions.GUID(), nullable=True))
        batch_op.create_index(batch_op.f('ix_annotation_contributor_guid'), ['contributor_guid'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_annotation_contributor_guid_user'), 'user', ['contributor_guid'], ['guid'])

    with op.batch_alter_table('asset', schema=None) as batch_op:
        batch_op.add_column(sa.Column('line_segments', app.extensions.JSON(), nullable=True))
        batch_op.add_column(sa.Column('classifications', app.extensions.JSON(), nullable=True))

    with op.batch_alter_table('mission', schema=None) as batch_op:
        batch_op.add_column(sa.Column('options', app.extensions.JSON(), nullable=False))
        batch_op.add_column(sa.Column('classifications', app.extensions.JSON(), nullable=True))
        batch_op.add_column(sa.Column('notes', sa.UnicodeText(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('mission', schema=None) as batch_op:
        batch_op.drop_column('notes')
        batch_op.drop_column('classifications')
        batch_op.drop_column('options')

    with op.batch_alter_table('asset', schema=None) as batch_op:
        batch_op.drop_column('classifications')
        batch_op.drop_column('line_segments')

    with op.batch_alter_table('annotation', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_annotation_contributor_guid_user'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_annotation_contributor_guid'))
        batch_op.drop_column('contributor_guid')

    op.create_table('mission_user_membership_enrollment',
    sa.Column('created', sa.DateTime(), autoincrement=False, nullable=False),
    sa.Column('updated', sa.DateTime(), autoincrement=False, nullable=False),
    sa.Column('viewed', sa.DateTime(), autoincrement=False, nullable=False),
    sa.Column('mission_guid', app.extensions.GUID(), autoincrement=False, nullable=False),
    sa.Column('user_guid', app.extensions.GUID(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['mission_guid'], ['mission.guid'], name='fk_mission_user_membership_enrollment_mission_guid_mission'),
    sa.ForeignKeyConstraint(['user_guid'], ['user.guid'], name='fk_mission_user_membership_enrollment_user_guid_user'),
    sa.PrimaryKeyConstraint('mission_guid', 'user_guid', name='pk_mission_user_membership_enrollment')
    )
    with op.batch_alter_table('mission_user_membership_enrollment', schema=None) as batch_op:
        batch_op.create_index('ix_mission_user_membership_enrollment_updated', ['updated'], unique=False)
        batch_op.create_index('ix_mission_user_membership_enrollment_created', ['created'], unique=False)

    with op.batch_alter_table('task_annotation_participation', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_task_annotation_participation_updated'))
        batch_op.drop_index(batch_op.f('ix_task_annotation_participation_created'))

    op.drop_table('task_annotation_participation')
    with op.batch_alter_table('task_user_assignment', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_task_user_assignment_updated'))
        batch_op.drop_index(batch_op.f('ix_task_user_assignment_created'))

    op.drop_table('task_user_assignment')
    with op.batch_alter_table('task_asset_participation', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_task_asset_participation_updated'))
        batch_op.drop_index(batch_op.f('ix_task_asset_participation_created'))

    op.drop_table('task_asset_participation')
    with op.batch_alter_table('mission_asset_participation', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_mission_asset_participation_updated'))
        batch_op.drop_index(batch_op.f('ix_mission_asset_participation_created'))

    op.drop_table('mission_asset_participation')
    with op.batch_alter_table('asset_tags', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_asset_tags_updated'))
        batch_op.drop_index(batch_op.f('ix_asset_tags_created'))

    op.drop_table('asset_tags')
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_task_updated'))
        batch_op.drop_index(batch_op.f('ix_task_owner_guid'))
        batch_op.drop_index(batch_op.f('ix_task_mission_guid'))
        batch_op.drop_index(batch_op.f('ix_task_created'))

    op.drop_table('task')
    with op.batch_alter_table('mission_user_assignment', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_mission_user_assignment_updated'))
        batch_op.drop_index(batch_op.f('ix_mission_user_assignment_created'))
    
    sa.Enum(name='tasktypes').drop(op.get_bind(), checkfirst=False)

    op.drop_table('mission_user_assignment')
    # ### end Alembic commands ###