"""empty message

Revision ID: dce7d7e06b22
Revises: 8a8e855a787a
Create Date: 2020-12-17 16:59:08.812040

"""

# revision identifiers, used by Alembic.
revision = 'dce7d7e06b22'
down_revision = '8a8e855a787a'

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils

import app
import app.extensions



def upgrade():
    pass


def downgrade():
    pass
