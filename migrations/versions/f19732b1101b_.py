# -*- coding: utf-8 -*-
"""empty message

Revision ID: f19732b1101b
Revises: 3badaaa870b5
Create Date: 2022-08-22 11:22:03.217037

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'f19732b1101b'
down_revision = '3badaaa870b5'


def upgrade():
    """
    Upgrade Semantic Description:
        Drops bitmask for data-manager role and gives those users admin role
    """
    # 1048576 (0x100000)  = data-manager bitmask
    # 16384 (0x4000)      = admin bitmask
    op.execute(
        'UPDATE "user" SET static_roles = static_roles & ~1048576 | 16384 WHERE static_roles & 1048576 > 0'
    )


def downgrade():
    """
    Downgrade Semantic Description:
        Upgrade is irreversible - no going back dude
    """
    pass
