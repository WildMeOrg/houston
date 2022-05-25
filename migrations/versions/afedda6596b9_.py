# -*- coding: utf-8 -*-
"""empty message

Revision ID: afedda6596b9
Revises: cc1f915cde87
Create Date: 2022-05-16 23:17:52.659466

"""
from alembic import op
import sqlalchemy as sa

import app
import app.extensions


# revision identifiers, used by Alembic.
revision = 'afedda6596b9'
down_revision = 'cc1f915cde87'


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('asset_group_sighting', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('progress_detection_guid', app.extensions.GUID(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                'progress_identification_guid', app.extensions.GUID(), nullable=True
            )
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_asset_group_sighting_progress_detection_guid_progress'),
            'progress',
            ['progress_detection_guid'],
            ['guid'],
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_asset_group_sighting_progress_identification_guid_progress'),
            'progress',
            ['progress_identification_guid'],
            ['guid'],
        )

    with op.batch_alter_table('git_store', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('progress_detection_guid', app.extensions.GUID(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                'progress_identification_guid', app.extensions.GUID(), nullable=True
            )
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_git_store_progress_detection_guid_progress'),
            'progress',
            ['progress_detection_guid'],
            ['guid'],
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_git_store_progress_identification_guid_progress'),
            'progress',
            ['progress_identification_guid'],
            ['guid'],
        )

    with op.batch_alter_table('progress', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sage_guid', app.extensions.GUID(), nullable=True))

    with op.batch_alter_table('annotation', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'progress_identification_guid', app.extensions.GUID(), nullable=True
            )
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_annotation_progress_identification_guid_progress'),
            'progress',
            ['progress_identification_guid'],
            ['guid'],
        )

    with op.batch_alter_table('sighting', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'progress_identification_guid', app.extensions.GUID(), nullable=True
            )
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_sighting_progress_identification_guid_progress'),
            'progress',
            ['progress_identification_guid'],
            ['guid'],
        )

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('progress', schema=None) as batch_op:
        batch_op.drop_column('sage_guid')

    with op.batch_alter_table('git_store', schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_git_store_progress_identification_guid_progress'),
            type_='foreignkey',
        )
        batch_op.drop_constraint(
            batch_op.f('fk_git_store_progress_detection_guid_progress'),
            type_='foreignkey',
        )
        batch_op.drop_column('progress_identification_guid')
        batch_op.drop_column('progress_detection_guid')

    with op.batch_alter_table('asset_group_sighting', schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_asset_group_sighting_progress_identification_guid_progress'),
            type_='foreignkey',
        )
        batch_op.drop_constraint(
            batch_op.f('fk_asset_group_sighting_progress_detection_guid_progress'),
            type_='foreignkey',
        )
        batch_op.drop_column('progress_identification_guid')
        batch_op.drop_column('progress_detection_guid')

    with op.batch_alter_table('sighting', schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_sighting_progress_identification_guid_progress'),
            type_='foreignkey',
        )
        batch_op.drop_column('progress_identification_guid')

    with op.batch_alter_table('annotation', schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_annotation_progress_identification_guid_progress'),
            type_='foreignkey',
        )
        batch_op.drop_column('progress_identification_guid')

    # ### end Alembic commands ###
