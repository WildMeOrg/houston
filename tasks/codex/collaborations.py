# -*- coding: utf-8 -*-
"""
Application collaborations management related tasks for Invoke.
"""

from tasks.utils import app_context_task


@app_context_task
def list_all(context):
    """
    Show existing collaborations.
    """
    from app.modules.collaborations.models import Collaboration

    collabs = Collaboration.query.all()
    for collab in collabs:
        users = collab.get_users()
        print(f'Collaboration : {collab} Users: {users} ')


@app_context_task
def list_user_collabs(context, email):
    """
    Show existing collaborations.
    """
    from app.modules.collaborations.models import CollaborationUserState
    from app.modules.users.models import User

    user = User.find(email=email)

    if user is None:
        print("User with email '%s' does not exist." % email)
        return

    for collab_assoc in user.get_collaboration_associations():
        users = collab_assoc.collaboration.get_users()
        if collab_assoc.read_approval_state == CollaborationUserState.CREATOR:
            print(f'Created Collaboration: {collab_assoc.collaboration} Users: {users}')
        else:
            print(f'Collaboration : {collab_assoc.collaboration} Users: {users} ')
