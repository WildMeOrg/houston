# -*- coding: utf-8 -*-
import logging

from flask import current_app
from gumby.models import Individual
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.extensions.celery import celery


log = logging.getLogger(__name__)


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        10.0 * 60, load_codex_indexes.s(), name='Load Elasticsearch Indexes'
    )


def create_wildbook_engine() -> Engine:
    """Creates a SQLAlchemy Engine for connecting to the Wildbook database"""
    return create_engine(current_app.config['WILDBOOK_DB_URI'])


@celery.task
def load_codex_indexes():
    wb_engine = create_wildbook_engine()
    with wb_engine.connect() as wb_conn:
        # Query for marked individual records
        results = wb_conn.execute(text(WILDBOOK_MARKEDINDIVIDUAL_SQL_QUERY))
        for result in results:
            # Create the document object
            indv = Individual(**result)
            # Assign the elasticsearch document identify
            indv.meta.id = f'markedindividual_{indv.id}'
            # Augment records with houston data points
            pass
            # Save document to elasticsearch
            indv.save(using=current_app.elasticsearch)


WILDBOOK_MARKEDINDIVIDUAL_SQL_QUERY = """\
SELECT
  -- id = UUIDField(required=True)
  mi."ID" as id,
  -- name = Keyword()
  multv."VALUES"::json->'*'->>0 as name,
  mi."NICKNAME" as nickname,
  -- alias = Keyword()
  multv."VALUES"::json->'Alternate ID'->>0 as alias,
  -- taxonomy = Keyword()
  tax."SCIENTIFICNAME" as taxonomy,
  -- last_sighting = Date()
  -- ... dynamically produced by elasticsearch via inspection of encounters
  -- sex = EnumField(Sex, required=False)
  lower(mi."SEX") as sex,
  -- birth = Date(required=False)
  mi."TIMEOFBIRTH" as birth,
  -- death = Date(required=False)
  mi."TIMEOFDEATH" as death,
  -- encounters = []
  array_to_json(array(select row_to_json(enc_row) from(
    SELECT
      -- id = UUIDField(required=True)
      e."ID" as id,
      -- point = GeoPoint(required=True)
      NULLIF((e."DECIMALLATITUDE"::float || ',' || e."DECIMALLONGITUDE")::text, ',') as point,
      -- animate_status = Keyword()
      -- sex = EnumField(Sex, required=False)
      lower(e."SEX") as sex,
      -- submitter_id = Keyword(required=True)
      'unknown' as submitter_id,
      -- ... unclear where this is going to be coming from; ownership is now in houston
      -- date_occurred = Date()
      (cdt."DATETIME"::timestamp || ' ' || cdt."TIMEZONE")::timestamp with time zone as date_occurred,
      -- taxonomy = Keyword()
      tax."SCIENTIFICNAME" as taxonomy,
      -- has_annotation = Boolean(required=True)
      true as has_annotation
      -- ... this point of data will be in houston
    FROM
      "MARKEDINDIVIDUAL_ENCOUNTERS" as mie
      left join "ENCOUNTER" as e on (mie."ID_EID" = e."ID")
      left join "TAXONOMY" as tax on (e."TAXONOMY_ID_OID" = tax."ID")
      left join "COMPLEXDATETIME" as cdt on (e."TIME_COMPLEXDATETIME_ID_OID" = cdt."COMPLEXDATETIME_ID")
    WHERE mie."ID_OID" = mi."ID"
  ) as enc_row)) as encounters
FROM
  "MARKEDINDIVIDUAL" as mi
  -- join for name
  left join "MULTIVALUE" as multv on (mi."NAMES_ID_OID" = multv."ID")
  -- join for genus and species
  left join "TAXONOMY" as tax on (mi."TAXONOMY_ID_OID" = tax."ID")
;
"""
