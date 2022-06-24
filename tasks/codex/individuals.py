# -*- coding: utf-8 -*-
"""
Application Individual related tasks for Invoke.
"""

from tasks.utils import app_context_task


@app_context_task
def list_all(context):
    """
    Show existing individuals.
    """
    from app.modules.individuals.models import Individual

    individuals = Individual.query.all()

    for individual in individuals:
        print(f'Individual : {individual}')


@app_context_task
def details(context, guid, debug=False):
    """
    Show full existing of a specific Individual.

    Command Line:
    > invoke codex.individals.details 00000000-0000-0000-0000-000000000002
    """
    if debug:
        breakpoint()

    import pprint

    from app.modules.individuals.models import Individual

    individual = Individual.query.get(guid)

    if individual is None:
        print(f'Individual {guid} not found')
        return

    # Just reuse the debug schema
    from app.modules.individuals.schemas import DebugIndividualSchema

    schema = DebugIndividualSchema()
    pprint.pprint(schema.dump(individual).data)


@app_context_task
def list_all_votes(context, debug=False):
    if debug:
        breakpoint()

    from app.modules.individuals.models import IndividualMergeRequestVote

    all_votes = IndividualMergeRequestVote.query.all()
    for vote in all_votes:
        print(f'Vote : {vote}')
