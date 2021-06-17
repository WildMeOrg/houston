# -*- coding: utf-8 -*-
import logging

import gumby
from flask import current_app
from flask_restx_patched import Parameters, Resource
from flask_marshmallow import base_fields

from app.extensions.api import api_v1, Namespace


log = logging.getLogger(__name__)
ns = Namespace('search', description='Search')


def init_app(app, **kwargs):
    api_v1.add_namespace(ns)


class IndividualSearchParameters(Parameters):
    # Sighting encouter date range
    sighting_start_date = base_fields.Date()
    sighting_end_date = base_fields.Date()

    # # Sighting location bounding box
    # sighting_bounding_box = base_fields.Tuple((
    #     base_fields.Tuple(
    #         (base_fields.Float, base_fields.Float,)
    #     ),
    #     base_fields.Tuple(
    #         (base_fields.Float, base_fields.Float,)
    #     ),
    # ))

    # Individual birth date range
    birth_start_date = base_fields.Date()
    birth_end_date = base_fields.Date()

    # Individual death date range
    death_start_date = base_fields.Date()
    death_end_date = base_fields.Date()

    # Individual attributes
    name = base_fields.String()
    species = base_fields.String()
    sex = base_fields.String()
    animate_status = base_fields.String()
    has_annotation = base_fields.Boolean()

    # ###
    # Query parameters
    QUERY_PARAMS = ('name',)

    # ###
    # Filter parameters
    FILTER_PARAMS = (
        'species',
        'sightings_start_date',
        'sightings_end_date',
        'birth_start_date',
        'birth_end_date',
        'death_start_date',
        'death_end_date',
        'sex',
        'animate_status',
        'has_annotation',
    )


@ns.route('/individuals')
class Individuals(Resource):
    @ns.parameters(IndividualSearchParameters())
    def post(self, args):
        s = gumby.Individual.search(using=current_app.elasticsearch)

        for query_param in IndividualSearchParameters.QUERY_PARAMS:
            value = args.get(query_param)
            if value:
                # fuzzy query match the value
                s = s.query('match', **{query_param: value})

        for filter_param in IndividualSearchParameters.FILTER_PARAMS:
            value = args.get(filter_param)
            if value:
                s = s.filter('term', **{filter_param: value})

        log.debug(f'elasticsearch query:  {s.to_dict()}')
        resp = s.execute()
        return resp.to_dict()
