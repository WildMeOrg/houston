# -*- coding: utf-8 -*-
import datetime

import pytz

from app.modules.auth.models import Code, CodeDecisions, CodeTypes


def test_Code(db, researcher_1):
    # Create a recover code
    recover_1 = Code.get(researcher_1, CodeTypes.recover)
    assert not recover_1.is_expired
    assert not recover_1.is_resolved
    assert Code.find_all(recover_1.accept_code) == [recover_1]
    assert Code.find_all(recover_1.reject_code) == [recover_1]
    assert recover_1.accept_code != recover_1.reject_code
    assert 'type=recover' in repr(recover_1)

    # Get the recover code (should not create a new one)
    recover_2 = Code.get(researcher_1, CodeTypes.recover)
    assert recover_1.guid == recover_2.guid

    # Force create another recover code
    recover_3 = Code.get(researcher_1, CodeTypes.recover, create_force=True)
    assert recover_1.guid != recover_3.guid

    # Get all the valid recover codes for the user
    assert Code.valid_codes(researcher_1, CodeTypes.recover) == [recover_3, recover_1]

    # Create another recover code and expire it
    recover_4 = Code.get(researcher_1, CodeTypes.recover, create_force=True)
    recover_4.expires = (
        datetime.datetime.now() - datetime.timedelta(seconds=1)
    ).astimezone(pytz.utc)
    with db.session.begin():
        db.session.merge(recover_4)

    # Valid recover codes for the user should not include expired code
    assert Code.valid_codes(researcher_1, CodeTypes.recover) == [recover_3, recover_1]

    # Accept code that doesn't exist
    assert Code.received('1') == (CodeDecisions.unknown, None)

    # Accept recover code 1
    assert Code.received(recover_1.accept_code) == (CodeDecisions.accept, recover_1)
    assert recover_1.is_resolved is True

    # Accept recover code 1 again
    assert Code.received(recover_1.accept_code) == (CodeDecisions.dismiss, recover_1)
    assert recover_1.is_resolved is True

    # Accept expired recovery code 4
    assert Code.received(recover_4.accept_code) == (CodeDecisions.expired, recover_4)
    assert recover_4.is_resolved is False

    # Replace recover code (delete all valid codes)
    recover_5 = Code.get(researcher_1, CodeTypes.recover, replace=True, replace_ttl=None)
    assert Code.valid_codes(researcher_1, CodeTypes.recover) == [recover_5]

    # Recover code 1 is already resolved so not replaced
    assert Code.query.get(recover_1.guid) == recover_1
    # Recover code 3 was valid so was replaced
    assert Code.query.get(recover_3.guid) is None
    # Recover code 4 is already expired so not replaced
    assert Code.query.get(recover_4.guid) == recover_4

    # Reject recover code 5
    assert Code.received(recover_5.reject_code) == (CodeDecisions.reject, recover_5)
    assert recover_5.is_resolved is True

    # No more valid recover codes for user
    assert Code.valid_codes(researcher_1, CodeTypes.recover) == []

    # Clean up expired but not resolved codes
    Code.cleanup()
    assert Code.query.get(recover_1.guid) == recover_1
    assert Code.query.get(recover_4.guid) is None

    # Delete other codes
    recover_1.delete()
    recover_5.delete()
