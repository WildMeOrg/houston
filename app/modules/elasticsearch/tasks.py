# -*- coding: utf-8 -*-
from contextlib import contextmanager
import logging

import json
from flask import current_app
from gumby.models import Individual, Encounter, Sighting
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from datetime import datetime, timedelta
from app.extensions.celery import celery
from app.modules.site_settings.models import SiteSetting


log = logging.getLogger(__name__)

zero_uuid = '00000000-0000-0000-0000-000000000000'


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        2.0 * 60, load_codex_indexes.s(), name='Load Elasticsearch Indexes'
    )


@contextmanager
def create_wildbook_engine() -> Engine:
    """Creates a SQLAlchemy Engine for connecting to the Wildbook database"""
    engine = create_engine(current_app.config['WILDBOOK_DB_URI'])
    try:
        yield engine
    finally:
        engine.dispose()


@contextmanager
def create_houston_engine() -> Engine:
    """Creates a SQLAlchemy Engine for connecting to the houston database"""
    engine = create_engine(current_app.config['SQLALCHEMY_DATABASE_URI'])
    try:
        yield engine
    finally:
        engine.dispose()


def set_up_houston_tables(wb_engine, h_engine):
    # Fetch houston enum types
    with h_engine.connect() as h_conn:
        results = h_conn.execute(text(ENUM_TYPE_LIST_SQL_QUERY))
        enum_list = results.fetchall()

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


def load_individuals_index(
    wb_engine,
    catchup_index_before=None,
    catchup_index_batch_size=0,
    catchup_index_mark=None,
):
    if catchup_index_before:
        where_clause = f"WHERE hind.updated < '{catchup_index_before}' AND hind.guid > '{catchup_index_mark}' ORDER BY hind.guid LIMIT {catchup_index_batch_size}"
    else:
        cutoff = update_incremental_cutoff('individual')
        where_clause = f"WHERE hind.updated >= '{cutoff}'"
    last_guid = None
    with wb_engine.connect() as wb_conn:
        # Query for marked individual records
        sql = WILDBOOK_MARKEDINDIVIDUAL_SQL_QUERY
        sql = sql.replace('{where_clause}', where_clause)
        results = wb_conn.execute(text(sql))
        for result in results:
            result = combine_names(result)
            # Create the document object
            indv = Individual(**result)
            # Assign the elasticsearch document identify
            indv.meta.id = f'markedindividual_{indv.id}'
            # Augment records with houston data points
            pass
            # Save document to elasticsearch
            indv.save(using=current_app.elasticsearch)
            last_guid = indv.id
    return last_guid


WILDBOOK_MARKEDINDIVIDUAL_SQL_QUERY = """\
SELECT
  -- id = UUIDField(required=True)
  mi."ID" as id,
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
  -- this all_names is deprecated in favor of name_dict
  -- array_to_json(array(select value from houston.name where individual_guid=hind.guid)) as all_names,
  -- houston-based names
  json_object(
    array(select context from houston.name where individual_guid=hind.guid order by houston.name.guid),
    array(select value from houston.name where individual_guid=hind.guid order by houston.name.guid)
  ) as name_dict,
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
  -- join for genus and species
  left join "TAXONOMY" as tax on (mi."TAXONOMY_ID_OID" = tax."ID")
  JOIN houston.individual hind ON mi."ID" = hind.guid::text
  {where_clause}
;
"""


def load_encounters_index(
    wb_engine,
    catchup_index_before=None,
    catchup_index_batch_size=0,
    catchup_index_mark=None,
):
    if catchup_index_before:
        where_clause = f"WHERE hen.updated < '{catchup_index_before}' AND hen.guid > '{catchup_index_mark}' ORDER BY hen.guid LIMIT {catchup_index_batch_size}"
    else:
        cutoff = update_incremental_cutoff('encounter')
        where_clause = f"WHERE hen.updated >= '{cutoff}'"
    last_guid = None
    with wb_engine.connect() as wb_conn:
        sql = ENCOUNTERS_INDEX_SQL
        sql = sql.replace('{where_clause}', where_clause)
        results = wb_conn.execute(text(sql))
        for row in results:
            result = combine_datetime(row)
            result = combine_customfields(result)
            # Create the document object
            encounter = Encounter(**result)
            # Assign the elasticsearch document identify
            encounter.meta.id = f'encounter_{encounter.id}'
            # Save document to elasticsearch
            encounter.save(using=current_app.elasticsearch)
            last_guid = encounter.id
    return last_guid


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
{where_clause}
"""


def load_sightings_index(
    wb_engine,
    catchup_index_before=None,
    catchup_index_batch_size=0,
    catchup_index_mark=None,
):
    if catchup_index_before:
        where_clause = f"WHERE si.updated < '{catchup_index_before}' AND si.guid > '{catchup_index_mark}'"
        order_clause = f'ORDER BY id LIMIT {catchup_index_batch_size}'
    else:
        cutoff = update_incremental_cutoff('sighting')
        where_clause = f"WHERE si.updated >= '{cutoff}'"
        order_clause = ''
    last_guid = None
    with wb_engine.connect() as wb_conn:
        sql = SIGHTINGS_INDEX_SQL
        sql = sql.replace('{where_clause}', where_clause)
        sql = sql.replace('{order_clause}', order_clause)
        results = wb_conn.execute(text(sql))
        for i, row in enumerate(results):
            result = combine_datetime(row)
            result = combine_customfields(result)
            # Create the document object
            sighting = Sighting(**result)
            # Assign the elasticsearch document identify
            sighting.meta.id = f'sighting_{sighting.id}'
            # Save document to elasticsearch
            sighting.save(using=current_app.elasticsearch)
            last_guid = sighting.id
    return last_guid


SIGHTINGS_INDEX_SQL = """\
SELECT
  oc."ID" AS id,
  NULLIF((oc."DECIMALLATITUDE"::float || ',' || oc."DECIMALLONGITUDE")::text, ',') AS point,
  NULLIF(array_agg(DISTINCT en."LOCATIONID"), '{NULL}') AS location_ids,
  NULLIF(array_agg(DISTINCT en."VERBATIMLOCALITY"), '{NULL}') AS verbatim_localities,
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
  ) AS custom_fields,
  (array_agg(DISTINCT hen.owner_guid))[1] AS owner
FROM
  "OCCURRENCE" oc
  LEFT JOIN "OCCURRENCE_ENCOUNTERS" oe ON oe."ID_OID" = oc."ID"
  LEFT JOIN "ENCOUNTER" en ON en."ID" = oe."ID_EID"
  LEFT JOIN "TAXONOMY" ta ON ta."ID" = en."TAXONOMY_ID_OID"
  JOIN houston.sighting si ON oc."ID" = si.guid::text
  LEFT JOIN houston.encounter hen ON si.guid = hen.sighting_guid
  LEFT JOIN houston.complex_date_time cdt ON si.time_guid = cdt.guid
{where_clause}
GROUP BY id, datetime, timezone, specificity
{order_clause}
"""


def combine_datetime(row):
    result = dict(row)
    if row['datetime']:
        result['datetime'] = datetime.fromisoformat(
            row['datetime'].isoformat() + result.pop('timezone')
        )
    return result


def combine_customfields(result):
    if result['custom_fields']:
        custom_fields = {}
        # [{"5fda2b91-d4aa-4f5e-9479-9845402a9386":"Giraffe"}]
        for field_value_dict in json.loads(result['custom_fields']):
            if not field_value_dict or not isinstance(field_value_dict, dict):
                continue
            for field, value in field_value_dict.items():
                if field in custom_fields:
                    if not isinstance(custom_fields[field], list):
                        custom_fields[field] = [custom_fields[field]]
                    custom_fields[field].append(value)
                else:
                    custom_fields[field] = value
        result['custom_fields'] = custom_fields
    return result


def combine_names(row):
    result = dict(row)
    if (
        'name_dict' in result
        and isinstance(result['name_dict'], dict)
        and len(result['name_dict'])
    ):
        names = []
        for context in result['name_dict']:
            # old-world seems to favor 'default', but new-world uses 'defaultName',
            #   so we let either of these get priority; if both exist, its luck of the draw
            if context == 'default' or context == 'defaultName':
                names.insert(0, result['name_dict'][context])
            else:
                names.append(result['name_dict'][context])
            result['name'] = names
    return result


def update_incremental_cutoff(key_prefix):
    dt_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    inc_key = f'elasticsearch_incremental_cutoff_{key_prefix}'
    cutoff = SiteSetting.get_string(inc_key)
    if not cutoff:
        cutoff = dt_now
    SiteSetting.set(inc_key, string=dt_now)
    log.info(f'incremental_cutoff [{key_prefix}] => {cutoff}, dt_now = {dt_now}')
    return cutoff


@celery.task
def load_codex_indexes():
    log.info('incremental indexing started')
    with create_wildbook_engine() as wb_engine:
        with create_houston_engine() as h_engine:
            set_up_houston_tables(wb_engine, h_engine)
        load_individuals_index(wb_engine)
        load_encounters_index(wb_engine)
        load_sightings_index(wb_engine)


def catchup_index_get():
    conf_key = 'elasticsearch_catchup_index_conf'
    conf = SiteSetting.get_json(conf_key)
    if not conf or 'before' not in conf:
        return
    # conf must have 'before' value; the rest can use these defaults
    def_conf = {
        'batch_size': 250,
        'batch_pause': 5,
        'encounter_mark': zero_uuid,
        'sighting_mark': zero_uuid,
        'individual_mark': zero_uuid,
    }
    def_conf.update(conf)
    return def_conf


def catchup_index_set(conf):
    if not conf or 'before' not in conf:
        return
    conf_key = 'elasticsearch_catchup_index_conf'
    SiteSetting.set(conf_key, data=conf)


@celery.task
def catchup_index_start():
    conf = catchup_index_get()
    if not conf:
        log.info('catchup_index_start found no conf -- bailing.')
        return
    log.info(f'catchup index commencing with: {conf}')

    last_guid_encounter = load_encounters_index(
        catchup_index_before=conf['before'],
        catchup_index_batch_size=conf['batch_size'],
        catchup_index_mark=conf['encounter_mark'] or zero_uuid,
    )
    conf['encounter_mark'] = last_guid_encounter
    log.debug(
        f"catchup index finished encounters batch (size={conf['batch_size']}) on guid {last_guid_encounter}"
    )

    last_guid_sighting = load_sightings_index(
        catchup_index_before=conf['before'],
        catchup_index_batch_size=conf['batch_size'],
        catchup_index_mark=conf['sighting_mark'] or zero_uuid,
    )
    conf['sighting_mark'] = last_guid_sighting
    log.debug(
        f"catchup index finished sightings batch (size={conf['batch_size']}) on guid {last_guid_sighting}"
    )

    last_guid_individual = load_individuals_index(
        catchup_index_before=conf['before'],
        catchup_index_batch_size=conf['batch_size'],
        catchup_index_mark=conf['individual_mark'] or zero_uuid,
    )
    conf['individual_mark'] = last_guid_individual
    log.debug(
        f"catchup index finished individuals batch (size={conf['batch_size']}) on guid {last_guid_individual}"
    )

    conf_check = catchup_index_get()  # if gone, means a reset() was submitted, so we bail
    if not conf_check:
        log.info(
            'catchup index batch cycle finished, but no conf found -- assumed reset, so STOPPING.'
        )
        return
    elif not last_guid_encounter and not last_guid_individual and not last_guid_sighting:
        catchup_index_reset()
        log.info(
            'catchup index finished all batches with no results.  ENDING CATCHUP INDEX.'
        )
        return
    else:
        log.info(
            f"catchup index finished all batches with more work to do; pausing {conf['batch_pause']} sec before next round"
        )
        catchup_index_set(conf)
        start_time = datetime.utcnow() + timedelta(seconds=conf['batch_pause'])
        catchup_index_start.apply_async(eta=start_time)


def catchup_index_reset():
    conf_key = 'elasticsearch_catchup_index_conf'
    SiteSetting.forget_key_value(conf_key)
