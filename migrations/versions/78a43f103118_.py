# -*- coding: utf-8 -*-
"""empty message

Revision ID: 78a43f103118
Revises: f19732b1101b
Create Date: 2022-08-24 16:29:47.874918

"""
import sqlalchemy as sa
from alembic import op

import app
import app.extensions

# revision identifiers, used by Alembic.
revision = '78a43f103118'
down_revision = 'f19732b1101b'


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'scout_annotation',
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.Column('updated', sa.DateTime(), nullable=False),
        sa.Column('indexed', sa.DateTime(), nullable=False),
        sa.Column('viewed', sa.DateTime(), nullable=False),
        sa.Column('version', sa.BigInteger(), nullable=True),
        sa.Column('content_guid', app.extensions.GUID(), nullable=True),
        sa.Column('autogenerated', sa.Boolean(), nullable=True),
        sa.Column('sage_job_id', app.extensions.GUID(), nullable=True),
        sa.Column('ia_class', sa.String(length=255), nullable=False),
        sa.Column('viewpoint', sa.String(length=255), nullable=False),
        sa.Column('bounds', app.extensions.JSON(), nullable=False),
        sa.Column('guid', app.extensions.GUID(), nullable=False),
        sa.Column('asset_guid', app.extensions.GUID(), nullable=False),
        sa.Column('contributor_guid', app.extensions.GUID(), nullable=True),
        sa.Column('inExport', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ['asset_guid'],
            ['asset.guid'],
            name=op.f('fk_scout_annotation_asset_guid_asset'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['contributor_guid'],
            ['user.guid'],
            name=op.f('fk_scout_annotation_contributor_guid_user'),
        ),
        sa.PrimaryKeyConstraint('guid', name=op.f('pk_scout_annotation')),
    )
    with op.batch_alter_table('scout_annotation', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_scout_annotation_asset_guid'), ['asset_guid'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_scout_annotation_contributor_guid'),
            ['contributor_guid'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_scout_annotation_created'), ['created'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_scout_annotation_indexed'), ['indexed'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_scout_annotation_updated'), ['updated'], unique=False
        )

    op.create_table(
        'scout_annotation_keywords',
        sa.Column('created', sa.DateTime(), nullable=False),
        sa.Column('updated', sa.DateTime(), nullable=False),
        sa.Column('indexed', sa.DateTime(), nullable=False),
        sa.Column('viewed', sa.DateTime(), nullable=False),
        sa.Column('annotation_guid', app.extensions.GUID(), nullable=False),
        sa.Column('keyword_guid', app.extensions.GUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ['annotation_guid'],
            ['scout_annotation.guid'],
            name=op.f('fk_scout_annotation_keywords_annotation_guid_scout_annotation'),
        ),
        sa.ForeignKeyConstraint(
            ['keyword_guid'],
            ['keyword.guid'],
            name=op.f('fk_scout_annotation_keywords_keyword_guid_keyword'),
        ),
        sa.PrimaryKeyConstraint(
            'annotation_guid', 'keyword_guid', name=op.f('pk_scout_annotation_keywords')
        ),
    )
    with op.batch_alter_table('scout_annotation_keywords', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_scout_annotation_keywords_created'), ['created'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_scout_annotation_keywords_indexed'), ['indexed'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_scout_annotation_keywords_updated'), ['updated'], unique=False
        )

    with op.batch_alter_table('annotation', schema=None) as batch_op:
        batch_op.add_column(sa.Column('autogenerated', sa.Boolean(), nullable=True))
        batch_op.add_column(
            sa.Column('sage_job_id', app.extensions.GUID(), nullable=True)
        )

    with op.batch_alter_table(
        'mission_task_annotation_participation', schema=None
    ) as batch_op:
        batch_op.drop_constraint(
            'fk_mission_task_annotation_participation_annotation_gui_ac14',
            type_='foreignkey',
        )
        batch_op.create_foreign_key(
            batch_op.f(
                'fk_mission_task_annotation_participation_annotation_guid_scout_annotation'
            ),
            'scout_annotation',
            ['annotation_guid'],
            ['guid'],
        )

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table(
        'mission_task_annotation_participation', schema=None
    ) as batch_op:
        batch_op.drop_constraint(
            batch_op.f(
                'fk_mission_task_annotation_participation_annotation_guid_scout_annotation'
            ),
            type_='foreignkey',
        )
        batch_op.create_foreign_key(
            'fk_mission_task_annotation_participation_annotation_gui_ac14',
            'annotation',
            ['annotation_guid'],
            ['guid'],
        )

    with op.batch_alter_table('annotation', schema=None) as batch_op:
        batch_op.drop_column('sage_job_id')
        batch_op.drop_column('autogenerated')

    with op.batch_alter_table('scout_annotation_keywords', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_scout_annotation_keywords_updated'))
        batch_op.drop_index(batch_op.f('ix_scout_annotation_keywords_indexed'))
        batch_op.drop_index(batch_op.f('ix_scout_annotation_keywords_created'))

    op.drop_table('scout_annotation_keywords')
    with op.batch_alter_table('scout_annotation', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_scout_annotation_updated'))
        batch_op.drop_index(batch_op.f('ix_scout_annotation_indexed'))
        batch_op.drop_index(batch_op.f('ix_scout_annotation_created'))
        batch_op.drop_index(batch_op.f('ix_scout_annotation_contributor_guid'))
        batch_op.drop_index(batch_op.f('ix_scout_annotation_asset_guid'))

    op.drop_table('scout_annotation')
    # ### end Alembic commands ###
