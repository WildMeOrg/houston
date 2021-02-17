"""Update submissionmajortype enum

Revision ID: 3c818cf3688c
Revises: 5854c14c634d
Create Date: 2021-02-17 00:27:10.599431

"""

# revision identifiers, used by Alembic.
revision = '3c818cf3688c'
down_revision = '5854c14c634d'

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils

import app
import app.extensions



def upgrade():
    """
    Upgrade Semantic Description:
        Change submissionmajortype enum to match the model.

        In migration f4f2436d30f2, the submissionmajortype was defined
        for the first time and didn't include "test".

        Then in migration a042326c4b51, the submissionmajortype enum is
        changed to include "test" but it was ignored and
        submissionmajortype still doesn't include "test" so this
        migration adds it.
    """
    if op.get_bind().dialect.name != 'postgresql':
        # This migration is only for postgresql
        return

    old_type = sa.Enum('filesystem', 'archive', 'service', 'unknown', 'error', 'reject', name='old_submissionmajortype')
    new_type = sa.Enum('filesystem', 'archive', 'service', 'test', 'unknown', 'error', 'reject', name='submissionmajortype')

    op.execute('ALTER TYPE submissionmajortype RENAME TO old_submissionmajortype')
    new_type.create(op.get_bind())
    op.execute('ALTER TABLE submission ALTER COLUMN major_type TYPE submissionmajortype USING major_type::text::submissionmajortype')
    old_type.drop(op.get_bind())


def downgrade():
    """
    Downgrade Semantic Description:
        Skip
    """
    pass
