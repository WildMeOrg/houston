# -*- coding: utf-8 -*-
"""empty message

Revision ID: 1d1db3bd11c9
Revises: cccf82faa3f9
Create Date: 2022-08-31 07:03:28.275036

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

import app
import app.extensions

# revision identifiers, used by Alembic.
revision = '1d1db3bd11c9'
down_revision = 'cccf82faa3f9'


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'scout_annotation',
        sa.Column('guid', app.extensions.GUID(), nullable=False),
        sa.Column('task_guid', app.extensions.GUID(), nullable=True),
        sa.Column('inExport', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ['guid'],
            ['annotation.guid'],
            name=op.f('fk_scout_annotation_guid_annotation'),
        ),
        sa.ForeignKeyConstraint(
            ['task_guid'],
            ['mission_task.guid'],
            name=op.f('fk_scout_annotation_task_guid_mission_task'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('guid', name=op.f('pk_scout_annotation')),
    )
    with op.batch_alter_table('scout_annotation', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_scout_annotation_task_guid'), ['task_guid'], unique=False
        )

    op.create_table(
        'codex_annotation',
        sa.Column('guid', app.extensions.GUID(), nullable=False),
        sa.Column('encounter_guid', app.extensions.GUID(), nullable=True),
        sa.Column('progress_identification_guid', app.extensions.GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ['encounter_guid'],
            ['encounter.guid'],
            name=op.f('fk_codex_annotation_encounter_guid_encounter'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['guid'],
            ['annotation.guid'],
            name=op.f('fk_codex_annotation_guid_annotation'),
        ),
        sa.ForeignKeyConstraint(
            ['progress_identification_guid'],
            ['progress.guid'],
            name=op.f('fk_codex_annotation_progress_identification_guid_progress'),
        ),
        sa.PrimaryKeyConstraint('guid', name=op.f('pk_codex_annotation')),
    )
    with op.batch_alter_table('codex_annotation', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_codex_annotation_encounter_guid'),
            ['encounter_guid'],
            unique=False,
        )

    # copy over codex annot stuff while we still have them
    with op.get_context().autocommit_block():
        op.execute(
            'INSERT INTO codex_annotation (guid, encounter_guid, progress_identification_guid) SELECT annot.guid, annot.encounter_guid, annot.progress_identification_guid FROM annotation annot'
        )

    with op.batch_alter_table('annotation', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('annotation_type', sa.String(length=32), nullable=True)
        )
        batch_op.drop_index('ix_annotation_encounter_guid')
        batch_op.drop_index('ix_annotation_task_guid')
        batch_op.drop_constraint(
            'fk_annotation_encounter_guid_encounter', type_='foreignkey'
        )
        batch_op.drop_constraint(
            'fk_annotation_progress_identification_guid_progress', type_='foreignkey'
        )
        batch_op.drop_constraint(
            'fk_annotation_task_guid_mission_task', type_='foreignkey'
        )
        batch_op.drop_column('task_guid')
        batch_op.drop_column('progress_identification_guid')
        batch_op.drop_column('inExport')
        batch_op.drop_column('encounter_guid')

    # set existing annotations to codex type
    with op.get_context().autocommit_block():
        op.execute(
            "UPDATE annotation SET annotation_type='codex_annotation' WHERE annotation_type IS NULL"
        )

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('annotation', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'encounter_guid', postgresql.UUID(), autoincrement=False, nullable=True
            )
        )
        batch_op.add_column(
            sa.Column('inExport', sa.BOOLEAN(), autoincrement=False, nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                'progress_identification_guid',
                postgresql.UUID(),
                autoincrement=False,
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column('task_guid', postgresql.UUID(), autoincrement=False, nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_annotation_task_guid_mission_task',
            'mission_task',
            ['task_guid'],
            ['guid'],
            ondelete='CASCADE',
        )
        batch_op.create_foreign_key(
            'fk_annotation_progress_identification_guid_progress',
            'progress',
            ['progress_identification_guid'],
            ['guid'],
        )
        batch_op.create_foreign_key(
            'fk_annotation_encounter_guid_encounter',
            'encounter',
            ['encounter_guid'],
            ['guid'],
            ondelete='CASCADE',
        )
        batch_op.create_index('ix_annotation_task_guid', ['task_guid'], unique=False)
        batch_op.create_index(
            'ix_annotation_encounter_guid', ['encounter_guid'], unique=False
        )
        batch_op.drop_column('annotation_type')

    with op.batch_alter_table('codex_annotation', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_codex_annotation_encounter_guid'))

    op.drop_table('codex_annotation')
    with op.batch_alter_table('scout_annotation', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_scout_annotation_task_guid'))

    op.drop_table('scout_annotation')
    # ### end Alembic commands ###
