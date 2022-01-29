# -*- coding: utf-8 -*-
import logging

import json
from flask import current_app
from gumby.models import Individual, Encounter, Sighting
from sqlalchemy import create_engine, text, MetaData, Table, Column, String, DateTime
from sqlalchemy.engine import Engine
from datetime import datetime
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


def create_houston_engine() -> Engine:
    """Creates a SQLAlchemy Engine for connecting to the houston database"""
    return create_engine(current_app.config['SQLALCHEMY_DATABASE_URI'])


def set_up_houston_tables():
    # Fetch houston enum types
    h_engine = create_houston_engine()
    with h_engine.connect() as h_conn:
        results = h_conn.execute(text(ENUM_TYPE_LIST_SQL_QUERY))
        enum_list = results.fetchall()

        # table with version info to determine if indexing is needed
        metadata = MetaData(h_engine)
        Table(
            'elasticsearch_metadata',
            metadata,
            Column('key', String, primary_key=True, nullable=False),
            Column('value_datetime', DateTime),
        )
        metadata.create_all()  # only will create if doesnt exist

    wb_engine = create_wildbook_engine()
    with wb_engine.connect() as wb_conn:
        # Create houston enum types
        results = wb_conn.execute(text(ENUM_TYPE_LIST_SQL_QUERY))
        wb_enum_list = dict(results.fetchall())
        for enum_name, enum_labels in enum_list:
            if enum_name not in wb_enum_list:
                enum_values = ', '.join(repr(label) for label in enum_labels)
                wb_conn.execute(text(f'CREATE TYPE {enum_name} AS ENUM ({enum_values})'))

        # Import houston tables if schema 'houston' doesn't exist
        if not wb_conn.execute(
            text(
                "SELECT * FROM information_schema.schemata WHERE schema_name = 'houston'"
            )
        ).fetchone():
            wb_conn.execute(text('CREATE EXTENSION IF NOT EXISTS postgres_fdw'))
            server_options = [f'dbname {repr(h_engine.url.database)}']
            user_mapping_options = [f'user {repr(h_engine.url.username)}']
            if h_engine.url.host:
                server_options.append(f'host {repr(h_engine.url.host)}')
            if h_engine.url.port:
                server_options.append(f'port {repr(h_engine.url.port)}')
            if h_engine.url.password:
                user_mapping_options.append(f'password {repr(h_engine.url.password)}')
            wb_conn.execute(
                text(
                    CREATE_SERVER_SQL
                    % {
                        'wb_user': wb_engine.url.username,
                        'server_options': ', '.join(server_options),
                        'user_mapping_options': ', '.join(user_mapping_options),
                    }
                )
            )


ENUM_TYPE_LIST_SQL_QUERY = """\
SELECT
  t.typname AS enum_name,
  array_agg(e.enumlabel) AS enum_labels
FROM
  pg_type t
  JOIN pg_enum e ON t.oid = e.enumtypid
GROUP BY enum_name
"""


CREATE_SERVER_SQL = """\
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

CREATE SERVER IF NOT EXISTS houston
FOREIGN DATA WRAPPER postgres_fdw
OPTIONS (%(server_options)s);

CREATE SCHEMA IF NOT EXISTS houston;

CREATE USER MAPPING IF NOT EXISTS FOR %(wb_user)s SERVER houston OPTIONS (%(user_mapping_options)s);

IMPORT FOREIGN SCHEMA public FROM SERVER houston INTO houston;
"""


def load_individuals_index():
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


def load_encounters_index():
    incremental_cutoff = update_incremental_cutoff('encounter')
    wb_engine = create_wildbook_engine()
    with wb_engine.connect() as wb_conn:
        sql = ENCOUNTERS_INDEX_SQL
        sql = sql.replace('{incremental_cutoff}', incremental_cutoff)
        results = wb_conn.execute(text(sql))
        log.debug(f'len results = {results.rowcount}')
        for row in results:
            result = combine_datetime(row)
            result = combine_customfields(result)
            # Create the document object
            encounter = Encounter(**result)
            # Assign the elasticsearch document identify
            encounter.meta.id = f'encounter_{encounter.id}'
            # Save document to elasticsearch
            encounter.save(using=current_app.elasticsearch)


ENCOUNTERS_INDEX_SQL = """\
SELECT
  en."ID" AS id,
  NULLIF((en."DECIMALLATITUDE"::float || ',' || en."DECIMALLONGITUDE")::text, ',') AS point,
  en."LOCATIONID" AS locationid,
  CASE WHEN en."SEX" = 'unk' THEN 'unknown'
       ELSE en."SEX"
  END AS sex,
  ta."SCIENTIFICNAME" AS taxonomy,
  en."LIVINGSTATUS" AS living_status,
  cdt.datetime AS datetime,
  -- timezone stored as "UTC+0300", change to "+03:00"
  left(right(cdt.timezone, 5), 3) || ':' || right(cdt.timezone, 2) AS timezone,
  cdt.specificity AS time_specificity,
  (SELECT
    NULLIF(
      array_to_json(array_agg((
        '{' ||
        to_json(cfv."DEFINITION_ID_OID") ||
        ':' ||
        coalesce(
          to_json(cfd."VALUE"),
          to_json(cfdo."VALUE"),
          to_json(cfi."VALUE"),
          to_json(cfs."VALUE")
        ) || '}')::json))::text,
      '[null]')
   FROM
    "APICUSTOMFIELDS_CUSTOMFIELDVALUES" cf
    LEFT JOIN "CUSTOMFIELDVALUEDATE" cfd ON cf."ID_EID" = cfd."ID"
    LEFT JOIN "CUSTOMFIELDVALUEDOUBLE" cfdo ON cf."ID_EID" = cfdo."ID"
    LEFT JOIN "CUSTOMFIELDVALUEINTEGER" cfi ON cf."ID_EID" = cfi."ID"
    LEFT JOIN "CUSTOMFIELDVALUESTRING" cfs ON cf."ID_EID" = cfs."ID"
    LEFT JOIN "CUSTOMFIELDVALUE" cfv ON cf."ID_EID" = cfv."ID"
   WHERE en."ID" = cf."ID_OID"
  ) AS custom_fields
FROM
  "ENCOUNTER" AS en
  LEFT JOIN "TAXONOMY" AS ta ON ta."ID" = en."TAXONOMY_ID_OID"
  JOIN houston.encounter hen ON en."ID" = hen.guid::text
  LEFT JOIN houston.complex_date_time cdt ON hen.time_guid = cdt.guid
WHERE
  hen.updated >= '{incremental_cutoff}'
"""


def load_sightings_index():
    wb_engine = create_wildbook_engine()
    with wb_engine.connect() as wb_conn:
        results = wb_conn.execute(text(SIGHTINGS_INDEX_SQL))
        for i, row in enumerate(results):
            result = combine_datetime(row)
            result = combine_customfields(result)
            # Create the document object
            sighting = Sighting(**result)
            # Assign the elasticsearch document identify
            sighting.meta.id = f'sighting_{sighting.id}'
            # Save document to elasticsearch
            sighting.save(using=current_app.elasticsearch)


SIGHTINGS_INDEX_SQL = """\
SELECT
  oc."ID" AS id,
  NULLIF((oc."DECIMALLATITUDE"::float || ',' || oc."DECIMALLONGITUDE")::text, ',') AS point,
  cdt.datetime AS datetime,
  -- timezone stored as "UTC+0300", change to "+03:00"
  left(right(cdt.timezone, 5), 3) || ':' || right(cdt.timezone, 2) AS timezone,
  cdt.specificity AS time_specificity,
  (array_agg(ta."SCIENTIFICNAME"))[1] AS taxonomy,
  oc."COMMENTS" AS comments,
  (SELECT
    NULLIF(
      array_to_json(array_agg((
        '{' ||
        to_json(cfv."DEFINITION_ID_OID") ||
        ':' ||
        coalesce(
          to_json(cfd."VALUE"),
          to_json(cfdo."VALUE"),
          to_json(cfi."VALUE"),
          to_json(cfs."VALUE")
        ) || '}')::json))::text,
      '[null]')
   FROM
    "APICUSTOMFIELDS_CUSTOMFIELDVALUES" cf
    LEFT JOIN "CUSTOMFIELDVALUEDATE" cfd ON cf."ID_EID" = cfd."ID"
    LEFT JOIN "CUSTOMFIELDVALUEDOUBLE" cfdo ON cf."ID_EID" = cfdo."ID"
    LEFT JOIN "CUSTOMFIELDVALUEINTEGER" cfi ON cf."ID_EID" = cfi."ID"
    LEFT JOIN "CUSTOMFIELDVALUESTRING" cfs ON cf."ID_EID" = cfs."ID"
    LEFT JOIN "CUSTOMFIELDVALUE" cfv ON cf."ID_EID" = cfv."ID"
   WHERE
    cf."ID_OID" = oc."ID"
  ) AS custom_fields
FROM
  "OCCURRENCE" oc
  LEFT JOIN "OCCURRENCE_ENCOUNTERS" oe ON oe."ID_OID" = oc."ID"
  LEFT JOIN "ENCOUNTER" en ON en."ID" = oe."ID_EID"
  LEFT JOIN "TAXONOMY" ta ON ta."ID" = en."TAXONOMY_ID_OID"
  JOIN houston.sighting si ON oc."ID" = si.guid::text
  LEFT JOIN houston.complex_date_time cdt ON si.time_guid = cdt.guid
GROUP BY id, datetime, timezone, specificity
"""


def combine_datetime(row):
    result = dict(row)
    if row['datetime']:
        result['datetime'] = datetime.datetime.fromisoformat(
            row['datetime'].isoformat() + result.pop('timezone')
        )
    return result


def combine_customfields(result):
    if result['custom_fields']:
        custom_fields = {}
        # [{"5fda2b91-d4aa-4f5e-9479-9845402a9386":"Giraffe"}]
        for field_value_dict in json.loads(result['custom_fields']):
            for field, value in field_value_dict.items():
                if field in custom_fields:
                    if not isinstance(custom_fields[field], list):
                        custom_fields[field] = [custom_fields[field]]
                    custom_fields[field].append(value)
                else:
                    custom_fields[field] = value
        result['custom_fields'] = custom_fields
    return result


def update_incremental_cutoff(key_prefix):
    dt_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cutoff = dt_now
    inc_key = f'{key_prefix}_incremental_cutoff'
    h_engine = create_houston_engine()
    with h_engine.connect() as h_conn:
        res = h_conn.execute(
            f"SELECT value_datetime FROM elasticsearch_metadata WHERE key='{inc_key}'"
        )
        if res.rowcount > 0:
            cutoff = res.first()[0].strftime('%Y-%m-%d %H:%M:%S')
            h_conn.execute(
                f"UPDATE elasticsearch_metadata SET value_datetime='{dt_now}' WHERE key='{inc_key}'"
            )
        else:
            h_conn.execute(
                f"INSERT INTO elasticsearch_metadata (key, value_datetime) VALUES ('{inc_key}', '{dt_now}')"
            )
    log.info(f'incremental_cutoff [{key_prefix}] => {cutoff}, dt_now = {dt_now}')
    return cutoff


@celery.task
def load_codex_indexes():
    set_up_houston_tables()
    # load_individuals_index()
    load_encounters_index()
    # load_sightings_index()
