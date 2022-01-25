# -*- coding: utf-8 -*-
"""adding sighting stage

Revision ID: 58bf0e49cbf7
Revises: adb5d1a314bc
Create Date: 2021-06-07 19:52:25.795223

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '58bf0e49cbf7'
down_revision = 'adb5d1a314bc'


new_options = ('detection', 'curation', 'processed', 'failed')
old_options = sorted(new_options + ('committed',))
old_type = sa.Enum(*old_options, name='assetgroupsightingstage')
new_type = sa.Enum(*new_options, name='assetgroupsightingstage')
tmp_type = sa.Enum(*new_options, name='_stage')

AssetGroupSighting = sa.sql.table(
    'asset_group_sighting', sa.Column('stage', new_type, nullable=False)
)


def upgrade():
    """
    Upgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """
    # Convert 'committed' stage into 'processed'
    op.execute(
        AssetGroupSighting.update()
        .where(AssetGroupSighting.c.stage == u'committed')
        .values(stage='processed')
    )

    if op.get_bind().dialect == 'postgresql':
        # Create a temporary "_stage" type, convert and drop the "old" type
        tmp_type.create(op.get_bind(), checkfirst=False)
        op.execute(
            'ALTER TABLE asset_group_sighting ALTER COLUMN stage TYPE _stage USING stage::TEXT::_stage'
        )
        old_type.drop(op.get_bind(), checkfirst=False)
        # Create and convert to the "new" stage type
        new_type.create(op.get_bind(), checkfirst=False)
        op.execute(
            'ALTER TABLE asset_group_sighting ALTER COLUMN stage TYPE assetgroupsightingstage USING stage::TEXT::assetgroupsightingstage'
        )
        tmp_type.drop(op.get_bind(), checkfirst=False)

    sightingstage = sa.Enum(
        'identification', 'un_reviewed', 'processed', 'failed', name='sightingstage'
    )
    sightingstage.create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table('sighting', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'stage',
                sightingstage,
                server_default=sa.text("'identification'"),
                nullable=False,
            )
        )

    # ### end Alembic commands ###


def downgrade():
    """
    Downgrade Semantic Description:
        ENTER DESCRIPTION HERE
    """

    with op.batch_alter_table('sighting', schema=None) as batch_op:
        batch_op.drop_column('stage')
    sa.Enum(name='sightingstage').drop(op.get_bind(), checkfirst=False)
    if op.get_bind().dialect == 'postgresql':
        # Create a temporary "_stage" type, convert and drop the "new" type
        tmp_type.create(op.get_bind(), checkfirst=False)
        op.execute(
            'ALTER TABLE asset_group_sighting ALTER COLUMN stage TYPE _stage USING stage::TEXT::_stage'
        )
        new_type.drop(op.get_bind(), checkfirst=False)
        # Create and convert to the "old" stage type
        old_type.create(op.get_bind(), checkfirst=False)
        op.execute(
            'ALTER TABLE asset_group_sighting ALTER COLUMN stage TYPE assetgroupsightingstage USING stage::TEXT::assetgroupsightingstage'
        )
        tmp_type.drop(op.get_bind(), checkfirst=False)
    # ### end Alembic commands ###
