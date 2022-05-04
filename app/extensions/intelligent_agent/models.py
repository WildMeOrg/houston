# -*- coding: utf-8 -*-
"""
IntelligentAgent (and subclass) models
--------------------------------------
"""
from datetime import datetime  # NOQA
import gettext
import traceback
import uuid
import enum
import logging

from app.extensions import db
import app.extensions.logging as AuditLog  # NOQA
from app.extensions import HoustonModel
from flask import current_app

log = logging.getLogger(__name__)  # pylint: disable=invalid-name
_ = gettext.gettext


class IntelligentAgentException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class IntelligentAgent:
    """
    Intelligent Agent base class
    """

    def collect(self):
        raise NotImplementedError('collect() must be overridden')

    def test_setup(self):
        log.warning('test_setup() must be overridden')
        return {'success': False}

    # appends necessary site-setting configs for intelligent agents
    @classmethod
    def site_setting_config_all(cls):
        config = {}
        for agent_cls in cls.get_agent_classes():
            config.update(agent_cls.site_setting_config())
        return config

    @classmethod
    def site_setting_config(cls):
        # every agent class needs the enabled setting
        return {
            cls.site_setting_id('enabled'): {
                'type': str,
                'default': None,
                'public': False,
                'edm_definition': {
                    'defaultValue': 'false',
                    'displayType': 'select',
                    'schema': {
                        'choices': [
                            {'label': 'Disabled', 'value': 'false'},
                            {'label': 'Enabled', 'value': 'true'},
                        ]
                    },
                },
            }
        }

    @classmethod
    def short_name(cls):
        return cls.__name__.lower()

    # probably want to override with something more general, like just 'twitter' etc
    @classmethod
    def social_account_key(cls):
        return cls.short_name()

    @classmethod
    def site_setting_id(cls, setting):
        return f'intelligent_agent_{cls.short_name()}_{setting}'

    # utility function that does the reverse of the above (trims off prefix)
    @classmethod
    def site_setting_id_short(cls, full_setting):
        prefix = f'intelligent_agent_{cls.short_name()}_'
        if full_setting.startswith(prefix):
            return full_setting[len(prefix) :]
        return full_setting

    @classmethod
    def get_site_setting_value(cls, setting):
        from app.modules.site_settings.models import SiteSetting

        return SiteSetting.get_value(cls.site_setting_id(setting))

    @classmethod
    def get_all_setting_values(cls):
        settings = {}
        for full_key in cls.site_setting_config():
            key = cls.site_setting_id_short(full_key)
            settings[key] = cls.get_site_setting_value(key)
        return settings

    @classmethod
    def is_enabled(cls):
        val = cls.get_site_setting_value('enabled')
        return bool(val and val.lower().startswith('t'))

    @classmethod
    def is_ready(cls):
        return cls.is_enabled()

    # TODO is there a programmatic way to do this?
    @classmethod
    def get_agent_classes(cls):
        from app.extensions.intelligent_agent.models import TwitterBot

        return [
            TwitterBot,
        ]

    @classmethod
    def get_agent_class_by_short_name(cls, short_name):
        for agent_cls in cls.get_agent_classes():
            if agent_cls.short_name() == short_name:
                return agent_cls
        return None

    @classmethod
    def set_persisted_value(cls, key, value):
        from app.utils import set_persisted_value

        full_key = f'intelligent_agent_{cls.short_name()}_{key}'
        log.debug(f'set_persisted_value({full_key}, {value})')
        return set_persisted_value(full_key, value)

    @classmethod
    def get_persisted_value(cls, key):
        from app.utils import get_persisted_value

        full_key = f'intelligent_agent_{cls.short_name()}_{key}'
        return get_persisted_value(full_key)


class IntelligentAgentContentState(str, enum.Enum):
    intake = 'intake'
    rejected = 'rejected'
    active = 'active'
    active_detection = 'active_detection'
    active_identification = 'active_identification'
    complete = 'complete'
    error = 'error'


class IntelligentAgentContent(db.Model, HoustonModel):
    """
    Intelligent Agent content (tweet, video, post, etc)
    """

    AGENT_CLASS = IntelligentAgent

    guid = db.Column(
        db.GUID, default=uuid.uuid4, primary_key=True
    )  # pylint: disable=invalid-name
    agent_type = db.Column(db.String(length=128), index=True, nullable=False)
    state = db.Column(
        db.Enum(IntelligentAgentContentState),
        default=IntelligentAgentContentState.intake,
        nullable=False,
        index=True,
    )
    owner_guid = db.Column(
        db.GUID,
        db.ForeignKey('user.guid'),
        index=True,
        nullable=True,
    )
    owner = db.relationship(
        'User',
        foreign_keys=[owner_guid],
    )
    source = db.Column(db.JSON, default=lambda: {}, nullable=False)
    raw_content = db.Column(db.JSON, default=lambda: {}, nullable=False)
    # data derived from raw_content, etc
    data = db.Column(db.JSON, default=lambda: {}, nullable=True)
    asset_group_guid = db.Column(
        db.GUID,
        db.ForeignKey('asset_group.guid'),
        index=True,
        nullable=True,
    )
    asset_group = db.relationship(
        'AssetGroup',
        foreign_keys='IntelligentAgentContent.asset_group_guid',
    )

    __mapper_args__ = {
        'confirm_deleted_rows': False,
        'polymorphic_identity': 'intelligent_agent',
        'polymorphic_on': agent_type,
    }

    def __init__(self, *args, **kwargs):
        self.agent_type = self.AGENT_CLASS.short_name()
        super().__init__(*args, **kwargs)

    def __repr__(self):
        return (
            '<{class_name}('
            'guid={self.guid}, state={self.state}, agent={self.agent_type}, '
            f'author={self.author_as_string()}'
            ')>'.format(class_name=self.__class__.__name__, self=self)
        )

    def respond_to(self, text):
        raise NotImplementedError('respond_to() must be overridden')

    # override
    # this should be what links to User via social_account_key()
    def get_author_id(self):
        return None

    def get_assets(self):
        if not self.asset_group:
            return None
        return self.asset_group.assets

    def get_asset_group_sighting(self):
        if not self.asset_group or not self.asset_group.asset_group_sightings:
            return None
        return self.asset_group.asset_group_sightings[0]

    def get_sighting(self):
        ags = self.get_asset_group_sighting()
        if not ags or not ags.sighting:
            return None
        return ags.sighting[0]

    def content_as_string(self):
        return str(self.raw_content)

    def source_as_string(self):
        return str(self.source)

    # should override with specifics to each agent (add twitter handle etc)
    def author_as_string(self):
        return f'{self.owner.guid}:{self.owner.full_name}' if self.owner else '[None]'

    def find_author_user(self):
        from app.modules.users.models import User

        return User.find_by_linked_account(
            self.AGENT_CLASS.social_account_key(),
            self.get_author_id(),
        )

    # can (should?) be overridden to be agent-specific if desired
    #   used for things like filename prefixes etc, so should be fairly "filename-friendly"
    def id_string(self):
        return str(self.guid)

    def get_reference_date(self):
        raise NotImplementedError('must be overridden')

    # probably useful for any agent, but agent can override if needed
    #   note: requires get_reference_date() to be defined for subclass
    def derive_time(self):
        from app.modules.complex_date_time.models import ComplexDateTime, Specificities
        from app.utils import nlp_parse_complex_date_time

        # be warned: falls back to current time now
        reference_date = (
            self.get_reference_date() or datetime.utcnow().isoformat() + '+00:00'
        )
        try:
            return nlp_parse_complex_date_time(
                self.content_as_string(), reference_date=reference_date
            )
        except RuntimeError as err:
            log.warning(
                f'nlp_parse_complex_date_time() probably does not have JRE/jars installed, using fallback; threw error: {str(err)}'
            )
        return ComplexDateTime.from_data(
            {
                'time': reference_date,
                'timeSpecificity': Specificities.time,
            }
        )

    # these search whole text, but can be overriden (e.g. with hashtags)
    #  wants a Taxonomy object
    def derive_taxonomy(self):
        from app.modules.site_settings.models import Taxonomy

        matches = Taxonomy.find_fuzzy_list(self.content_as_string().split())
        if not matches:
            return None
        return matches[0]

    # wants just a location_id as string
    def derive_location_id(self):
        from app.modules.site_settings.models import Regions

        reg = Regions()
        matches = reg.find_fuzzy_list(self.content_as_string().split())
        if not matches:
            return None
        log.debug(f'derive_location_id() found {matches}')
        return matches[0]['id']

    def get_species_detection_models(self):
        # FIXME some magic to derive via taxonomy (on .data)
        return ['african_terrestrial']

    # this validates and sets data, and creates AssetGroup
    #   will return (success, error-message)
    # probably want to use these rather than the pieces below (which are separate
    #   to allow for overriding if needed)
    def assemble(self):
        import traceback

        ok, err = self.validate_and_set_data()
        if not ok:
            return ok, err
        try:
            ag_metadata = self.generate_asset_group_metadata()
        except Exception as ex:
            log.error(
                f'assemble() on {self} had problems generating AssetGroup metadata: {str(ex)}'
            )
            log.debug(traceback.format_exc())
            return False, _('Problem preparing data')
        try:
            self.generate_asset_group(ag_metadata)
        except Exception as ex:
            log.error(
                f'assemble() on {self} had problems generating AssetGroup: {str(ex)}'
            )
            log.debug(traceback.format_exc())
            return False, _('Problem processing images')
        return True, None

    # see assemble()
    def validate_and_set_data(self):
        if not hasattr(self, '_transaction_paths') or not self._transaction_paths:
            return False, _('You must include at least one image.')
        data = {}
        tx = self.derive_taxonomy()
        if not tx:
            return False, _('You must include the species as a hashtag.')
        data['taxonomy_guid'] = tx.guid
        loc = self.derive_location_id()
        if not loc:
            return False, _('You must include the location ID as a hashtag.')
        data['location_id'] = loc
        cdt = self.derive_time()
        if not cdt:
            return False, _('You must tell us when this occurred.')
        data['time'] = cdt.isoformat_in_timezone()
        data['time_specificity'] = cdt.specificity.value
        data.update(self.data or {})
        self.data = data
        return True, None

    # see assemble()
    # this assumes validate_and_set_data() is run
    def generate_asset_group_metadata(self):
        assert self._transaction_id
        assert self._transaction_paths
        meta = {
            'speciesDetectionModel': self.get_species_detection_models(),
            'uploadType': 'form',
            'description': f'{self.AGENT_CLASS.short_name()}: [{self.guid}] {self.content_as_string()}',
            'transactionId': self._transaction_id,
            'sightings': [
                {
                    'assetReferences': self._transaction_paths,
                    'comments': self.content_as_string(),
                    'speciesDetectionModel': self.get_species_detection_models(),
                    'locationId': self.data.get('location_id'),
                    'taxonomy': self.data.get('taxonomy_guid'),
                    'time': self.data.get('time'),
                    'timeSpecificity': self.data.get('time_specificity'),
                    'encounters': [
                        {
                            'locationId': self.data.get('location_id'),
                            'taxonomy': self.data.get('taxonomy_guid'),
                            'time': self.data.get('time'),
                            'timeSpecificity': self.data.get('time_specificity'),
                        }
                    ],
                }
            ],
        }
        return meta

    # media_data is currently a list of dicts, that must have a url and optionally `id`
    #   this gets them to the transaction dir so they can be used by generate_asset_group
    #   sets self._transaction_paths for this purpose -- which is validated by validate_and_set_data()
    def prepare_media_transaction(self, media_data):
        if not isinstance(media_data, list) or not media_data:
            raise ValueError('invalid or empty media_data')
        import requests
        import uuid
        import os
        from app.extensions.tus import tus_upload_dir, tus_write_file_metadata
        from app.utils import get_stored_filename

        # basically replicate tus transaction dir, to drop files in
        self._transaction_id = str(uuid.uuid4())
        target_dir = tus_upload_dir(current_app, transaction_id=self._transaction_id)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        ct = 0
        self._transaction_paths = []
        for md in media_data:
            if not isinstance(md, dict):
                raise ValueError('media_data element is not a dict')
            url = md.get('url')
            if not url:
                raise ValueError(f'no url in {md}')
            original_filename = f"{self.id_string()}-{md.get('id', 'unknown')}-{ct}"
            self._transaction_paths.append(original_filename)
            target_path = os.path.join(target_dir, get_stored_filename(original_filename))
            log.debug(f'trying get {url} -> {target_path}')
            resp = requests.get(url)
            open(target_path, 'wb').write(resp.content)
            tus_write_file_metadata(target_path, original_filename)
            ct += 1
        log.debug(f'prepare_media_transaction() processed {self._transaction_paths}')
        return self._transaction_paths

    # this has all sorts of exceptions one might get
    def generate_asset_group(self, metadata_json):
        import app.extensions.logging as AuditLog  # NOQA
        from app.extensions.elapsed_time import ElapsedTime
        from app.modules.asset_groups.models import AssetGroup, AssetGroupMetadata

        assert isinstance(metadata_json, dict)
        timer = ElapsedTime()
        metadata = AssetGroupMetadata(metadata_json)
        metadata.process_request()
        metadata.owner = self.owner  # override!
        self.asset_group = AssetGroup.create_from_metadata(metadata)
        # this should kick off detection
        self.state = IntelligentAgentContentState.active_detection
        self.asset_group.begin_ia_pipeline(metadata)
        AuditLog.user_create_object(log, self.asset_group, duration=timer.elapsed())
        return self.asset_group

    def wait_for_detection_results(self):
        from app.extensions.intelligent_agent.tasks import (
            intelligent_agent_wait_for_detection_results,
        )

        args = (self.guid,)
        async_res = intelligent_agent_wait_for_detection_results.apply_async(args)
        log.debug(
            f'kicked off background wait_for_detection {self} async_res => {async_res}'
        )
        return async_res

    def detection_complete_on_asset(self, asset, jobs):
        log.debug(
            f'intelligent_agent: detection complete on {asset} with {jobs} for {self}'
        )

    def detection_timed_out(self):
        log.warning(f'intelligent_agent: never received detection results on {self}')
        self.state = IntelligentAgentContentState.error
        self.respond_to(
            _('We are sorry, there was a problem in finding something in your image.')
        )
        self.data['_error'] = 'detection timed out'
        with db.session.begin():
            db.session.merge(self)
        db.session.refresh(self)

    def detection_complete(self):
        from app.modules.assets.models import Asset
        import traceback

        annots = []
        jobs = []
        found_exception = False
        for asset in self.get_assets():
            annots += asset.annotations
            # in a perfect world, there is only 1 job per asset, but lets not assume that. :(
            ajobs = Asset.get_jobs_for_asset(asset.guid, True)
            assert ajobs, 'Very weird; jobs empty on completed detection'
            for j in ajobs:
                resp_status = j.get('response', {}).get('status')
                j_id = j.get('job_id')
                log.debug(f'job id={j_id} status={resp_status}')
                if resp_status == 'exception':
                    log.warning(
                        f"exception in detection response for {asset}: {j.get('response')}"
                    )
                    found_exception = True
            # this will be array of arrays
            jobs.append(ajobs)
        log.debug(
            f'intelligent_agent: detection fully completed on {self} with {len(annots)} annotations (found_exception={found_exception})'
        )
        if found_exception:
            self.state = IntelligentAgentContentState.error
            self.respond_to(
                _('We are sorry, there was a problem in finding something in your image.')
            )
            self.data['_error'] = 'detection timed out'
            self.data = self.data
            with db.session.begin():
                db.session.merge(self)
            db.session.refresh(self)
        elif len(annots) < 1:
            self.state = IntelligentAgentContentState.rejected
            self.respond_to(_('We could not find anything in your image, sorry.'))
            self.data['_rejection_error'] = 'no annotations found by detection'
            self.data = self.data
            with db.session.begin():
                db.session.merge(self)
            db.session.refresh(self)
        elif len(annots) > 1:
            self.state = IntelligentAgentContentState.complete
            if self.owner and not self.owner.is_public_user():
                # FIXME spec says we should provide link and image with annotations!?
                self.respond_to(
                    _(
                        'We found more than one animal. You must login and curate this data.'
                    )
                )
            else:
                self.respond_to(
                    _(
                        'We found more than one animal. This submission will be curated by a researcher.'
                    )
                )
        else:  # must be exactly 1 annot - on to identification!
            try:
                # will make real sighting/encounter and kick off identification
                self.commit_to_sighting(annots[0])
            except Exception as ex:
                log.error(
                    f'detection_complete() commit_to_sighting failed on {self} with: {str(ex)}'
                )
                trace = traceback.format_exc()
                log.debug(trace)
                self.state = IntelligentAgentContentState.error
                self.data['_error'] = 'commit_to_sighting error: ' + str(ex)
                self.data['_trace'] = trace
                self.data = self.data
                with db.session.begin():
                    db.session.merge(self)
                db.session.refresh(self)
                self.respond_to(_('We had a problem processing your submission, sorry.'))
                return

            self.state = IntelligentAgentContentState.active_identification
            with db.session.begin():
                db.session.merge(self)
            db.session.refresh(self)
            self.wait_for_identification_results()

    def commit_to_sighting(self, annot):
        assert self.asset_group and self.asset_group.asset_group_sightings
        ags = self.asset_group.asset_group_sightings[0]
        assert ags.config['encounters']
        log.debug(
            f'setting single annot {annot} into encounter on AssetGroupSighting {str(ags.guid)} in {self}'
        )
        ags.config['encounters'][0]['annotations'] = [str(annot.guid)]
        ags.config = ags.config
        with db.session.begin():
            db.session.merge(ags)
        db.session.refresh(ags)
        sighting = ags.commit()
        log.debug(f'{sighting} created via ags.commit() on {self}')
        return sighting

    def wait_for_identification_results(self):
        from app.extensions.intelligent_agent.tasks import (
            intelligent_agent_wait_for_identification_results,
        )

        args = (self.guid,)
        async_res = intelligent_agent_wait_for_identification_results.apply_async(args)
        log.debug(
            f'kicked off background wait_for_identification {self} async_res => {async_res}'
        )
        return async_res

    def identification_timed_out(self):
        log.warning(f'intelligent_agent: never received identification results on {self}')
        self.state = IntelligentAgentContentState.error
        # could send them link to see it anyway?
        self.respond_to(_('We are sorry, there was a problem matching your image.'))
        self.data['_error'] = 'identification timed out'
        with db.session.begin():
            db.session.merge(self)
        db.session.refresh(self)

    def identification_complete(self):
        from app.utils import full_api_url

        sighting = self.get_sighting()
        assert sighting, f'no sighting for {self}'
        url = full_api_url(f'sightings/{str(sighting.guid)}')
        log.warning(
            f'intelligent_agent: completed identification for {sighting} on {self}'
        )
        self.state = IntelligentAgentContentState.complete
        self.respond_to(
            _('We finished processing your submission. Check it out here: ') + url
        )
        with db.session.begin():
            db.session.merge(self)
        db.session.refresh(self)


class TwitterBot(IntelligentAgent):
    """
    TwitterBot intelligent Agent
    """

    # note, `api` is for V1 Twitter API and `client` if for V2; we obtain both, but probably should
    #   only use V2 unless we have no choice. i think?  more notes at get_api() and get_client()
    api = None
    client = None

    def __init__(self, *args, **kwargs):
        if not self.is_ready():
            raise ValueError('TwitterBot not ready for usage.')
        self.api = self.get_api()
        self.client = self.get_client()
        log.debug(f'TwitterBot() obtained {self.api} and {self.client}')
        super().__init__(*args, **kwargs)

    # this is uses only V2 calls
    def test_setup(self):
        if not self.is_enabled():
            return {'success': False, 'message': 'Not enabled.'}
        if not self.is_ready():
            return {'success': False, 'message': 'Not ready.'}
        if not self.client:
            return {'success': False, 'message': 'client unset.'}
        try:
            # twitter_settings = self.api.get_settings()
            me_data = self.client.get_me()
            assert me_data
            assert me_data.data
            assert me_data.data.username
        except Exception as ex:
            log.warning(f'TwitterBot.test_setup() client call got exception: {str(ex)}')
            return {'success': False, 'message': f'client exception: {str(ex)}'}
        log.debug(
            f'TwitterBot.test_setup() client.get_me() successfully returned: {me_data.data}'
        )
        return {
            'success': True,
            'message': f"Success: Twitter username is '{me_data.data.username}', name is '{me_data.data.name}'.",
            'username': me_data.data.username,
            'name': me_data.data.name,
        }

    # since_id=None will trigger finding tweets *since last attempt*
    #   a since_id value must be set to change this behavior
    #   (a negative number will disable since_id)
    def collect(self, since_id=None):
        assert self.client
        query = self.search_string()
        if not since_id:
            since_id = self.get_persisted_value('since_id')
        elif since_id < 0:
            since_id = None
        res = self.client.search_recent_tweets(
            query,
            since_id=since_id,
            tweet_fields=['created_at', 'author_id', 'entities', 'attachments'],
            expansions=['attachments.media_keys', 'author_id'],
            media_fields=['url', 'height', 'width', 'alt_text'],
        )
        tweets = []
        if not res.data or len(res.data) < 1:
            log.debug(
                f'collect(since_id={since_id}) on {self} retrieved no tweets with query "{query}"'
            )
            return tweets
        log.info(
            f'collect(since_id={since_id}) on {self} retrieved {len(res.data)} tweet(s) with query "{query}"'
        )
        latest_id = 0
        for twt in res.data:
            if twt.id > latest_id:
                latest_id = twt.id
            try:
                tt = TwitterTweet(twt, res.includes)
            except Exception as ex:
                log.warning(f'failed to process_tweet for {twt} due to: {str(ex)}')
                log.debug(traceback.format_exc())
                self.create_tweet_queued(
                    _('We could not process your tweet: ') + str(ex),
                    in_reply_to=twt.id,
                )
                continue

            # validates and creates tt.asset_group
            ok, err = tt.assemble()
            if ok:
                tt.state = IntelligentAgentContentState.active
                tt.respond_to(_('Thank you!  We are processing your tweet.'))
                tweets.append(tt)
            else:
                tt.state = IntelligentAgentContentState.rejected
                tt.data['_rejection_error'] = err
                tt.respond_to(_('Sorry, we cannot process this tweet because: ') + err)
            with db.session.begin():
                db.session.add(tt)
            if ok:
                tt.wait_for_detection_results()
        self.set_persisted_value('since_id', latest_id)
        return tweets

    # this should be used with caution -- use create_tweet_queued() to be safer
    def create_tweet_direct(self, text, in_reply_to=None):
        assert self.client
        assert text
        # this helps prevent sending identical outgoing (and may help dbugging?)
        stamp = str(uuid.uuid4())[0:4]
        text += '   ' + stamp
        log.info(f'create_tweet_direct(): {self} tweeting [re: {in_reply_to}] >>> {text}')
        if (
            not self.is_enabled()
            or self.get_persisted_value('twitter_outgoing_disabled') == 'true'
        ):
            log.warning('create_tweet_direct(): OUTGOING DISABLED')
            return
        tweet = self.client.create_tweet(text=text, in_reply_to_tweet_id=in_reply_to)
        log.debug(f'create_tweet_direct(): success tweeting {tweet}')
        return tweet

    # preferred usage (vs create_tweet_direct()) as it will throttle outgoing rate to
    #   hopefully keep twitter guards happy
    def create_tweet_queued(self, text, in_reply_to=None):
        from app.extensions.intelligent_agent.tasks import twitterbot_create_tweet_queued

        log.debug(f'{self} queueing tweet [re: {in_reply_to}] -- {text}')
        args = (text, in_reply_to)
        async_res = twitterbot_create_tweet_queued.apply_async(args)
        log.debug(f'{self} async_res => {async_res}')
        return async_res

    @classmethod
    def get_periodic_interval(cls):
        seconds = 30
        try:
            seconds = int(cls.get_site_setting_value('polling_interval'))
        except Exception as ex:
            log.warning(f'unable to get polling_interval: {str(ex)}')
            pass
        return seconds

    @classmethod
    def social_account_key(cls):
        return 'twitter'

    # right now we search tweets for only "@USERNAME" references, but this
    #    could be expanded to include some site-setting customizations
    def search_string(self):
        return f'@{self.get_username()}'

    def get_username(self):
        # could possibly set this as a (read-only) SiteSetting so we dont have to hit api every time
        assert self.client
        me_data = self.client.get_me()
        assert me_data
        assert me_data.data
        return me_data.data.username

    @classmethod
    def is_ready(cls):
        if not cls.is_enabled():
            log.info('TwitterBot.is_ready(): agent not enabled.')
            return False
        # this required-field stuff could be generalized to base class with required:True on config?
        settings = cls.get_all_setting_values()
        required = [
            'consumer_key',
            'consumer_secret',
            'access_token',
            'access_token_secret',
            'bearer_token',
        ]
        missing = []
        for key in required:
            if not settings.get(key):
                missing.append(key)
        if missing:
            log.info(f'TwitterBot.is_ready(): required settings missing: {missing}')
            return False
        return True

    @classmethod
    def site_setting_config(cls):
        config = super().site_setting_config()  # gets us the 'enabled' config
        config.update(
            {
                cls.site_setting_id('consumer_key'): {
                    'type': str,
                    'default': None,
                    'public': False,
                },
                cls.site_setting_id('consumer_secret'): {
                    'type': str,
                    'default': None,
                    'public': False,
                },
                cls.site_setting_id('access_token'): {
                    'type': str,
                    'default': None,
                    'public': False,
                },
                cls.site_setting_id('access_token_secret'): {
                    'type': str,
                    'default': None,
                    'public': False,
                },
                cls.site_setting_id('bearer_token'): {
                    'type': str,
                    'default': None,
                    'public': False,
                },
                cls.site_setting_id('polling_interval'): {
                    'type': str,
                    'default': None,
                    'public': False,
                    'edm_definition': {
                        'defaultValue': '30',
                        'displayType': 'select',
                        'schema': {
                            'choices': [
                                {'label': '30 seconds', 'value': '30'},
                                {'label': '1 minute', 'value': '60'},
                                {'label': '3 minutes', 'value': '180'},
                                {'label': '10 minutes', 'value': '600'},
                                {'label': '1 hour', 'value': '3600'},
                            ]
                        },
                    },
                },
            }
        )
        return config

    # uses Twitter API v1
    # https://docs.tweepy.org/en/latest/api.html
    def get_api(self):
        if not self.is_ready():
            raise ValueError('TwitterBot get_api(): not ready for usage.')
        import tweepy

        settings = self.get_all_setting_values()
        auth = tweepy.OAuth1UserHandler(
            settings.get('consumer_key'),
            settings.get('consumer_secret'),
            settings.get('access_token'),
            settings.get('access_token_secret'),
        )
        return tweepy.API(auth)

    # preferred(?) Twitter API v2 Client
    # https://docs.tweepy.org/en/latest/client.html
    def get_client(self):
        if not self.is_ready():
            raise ValueError('TwitterBot get_api(): not ready for usage.')
        import tweepy

        settings = self.get_all_setting_values()
        return tweepy.Client(
            settings.get('bearer_token'),
            settings.get('consumer_key'),
            settings.get('consumer_secret'),
            settings.get('access_token'),
            settings.get('access_token_secret'),
        )


class TwitterTweet(IntelligentAgentContent):
    AGENT_CLASS = TwitterBot

    __mapper_args__ = {
        'polymorphic_identity': 'twitterbot',
    }

    # https://docs.tweepy.org/en/latest/v2_models.html#tweet
    def __init__(self, tweet=None, response_includes=None, *args, **kwargs):
        from app.modules.users.models import User

        super().__init__(*args, **kwargs)
        if not tweet:
            return
        self._tweet = tweet
        self._resinc = response_includes
        author_data = {'id': tweet.author_id}
        if (
            response_includes
            and 'users' in response_includes
            and len(response_includes['users'])
        ):
            author_data = response_includes['users'][0].data
        self.source = {
            'id': tweet.id,
            'author': author_data,
        }
        self.raw_content = tweet.data
        self.owner = self.find_author_user()
        if not self.owner:
            self.owner = User.get_public_user()
            log.info(f'{tweet.id}: {author_data} no match in users; assigned public')

        # we prep the attachments for being made into AssetGroup if everything is successful
        if tweet.attachments:
            media_data = []
            if not response_includes:
                log.error(f'attachments with no response_includes: tweet {tweet.id}')
            elif 'media' not in response_includes or not response_includes['media']:
                log.error(
                    f'attachments with no media in response_includes: tweet {tweet.id}'
                )
            elif 'media_keys' not in tweet.attachments:
                log.error(f'attachments with no media_keys: tweet {tweet.id}')
            else:  # try to map attachments to media
                for media in response_includes['media']:
                    if media.media_key in tweet.attachments['media_keys']:
                        log.debug(
                            f'{media.media_key} FOUND in attachments on tweet {tweet.id}: {media.data}'
                        )
                        # so generate_asset_group() can use media_key as media "id"
                        media.data['id'] = media.media_key
                        media_data.append(media.data)
                    else:
                        log.debug(
                            f'{media.media_key} not in attachments on tweet {tweet.id}'
                        )
            try:
                # this sets self._transaction_paths (if all good)
                self.prepare_media_transaction(media_data)
            except Exception as ex:
                log.warning(
                    f'failed prepare_media_transaction() on tweet {tweet.id}: {str(ex)}'
                )
                log.debug(traceback.format_exc())

    # (Pdb) abc[0].raw_content
    # {'id': '1516841133871038464', 'entities': {'mentions': [{'start': 7, 'end': 19, 'username': 'TweetABruce', 'id': '986683924905521152'}], 'urls': [{'start': 88, 'end': 111, 'url': 'https://t.co/eGDgc8FkVI', 'expanded_url': 'https://twitter.com/CitSciBot/status/1516841133871038464/photo/1', 'display_url': 'pic.twitter.com/eGDgc8FkVI'}], 'hashtags': [{'start': 44, 'end': 51, 'tag': 'grevys'}], 'annotations': [{'start': 82, 'end': 86, 'probability': 0.9708, 'type': 'Place', 'normalized_text': 'kenya'}]}, 'attachments': {'media_keys': ['3_1516841098055802880']}, 'text': 'ugh ok @TweetABruce lemme try some hashtags #grevys from my sighting yesterday in kenya https://t.co/eGDgc8FkVI', 'created_at': '2022-04-20T18:08:02.000Z', 'author_id': '989923960295866368'}

    def id_string(self):
        if self.source:
            return f"tweetmedia-{self.source.get('id', 'unknown')}-{self.guid}"
        return f'tweetmedia-unknown-{self.guid}'

    def get_author_id(self):
        return self.source.get('author', {}).get('id') if self.source else None

    def get_author_username(self):
        return self.source.get('author', {}).get('username') if self.source else None

    def content_as_string(self):
        return self.raw_content.get('text')

    def author_as_string(self):
        author = super().author_as_string()
        uname = self.get_author_username()
        return f'{author}:{uname}' if uname else author

    # isoformat string
    def get_reference_date(self):
        return self.raw_content.get('created_at', '').replace('Z', '+00:00')

    def respond_to(self, text):
        log.debug(f'responding to {self} from {self.get_author_username()}: {text}')
        assert self.source and self.source.get('id')
        tb = TwitterBot()
        tb.create_tweet_queued(text, in_reply_to=self.source.get('id'))

    def hashtag_values(self):
        if not self.raw_content.get('entities') or not isinstance(
            self.raw_content['entities'].get('hashtags'), list
        ):
            return []
        values = []
        for ht in self.raw_content['entities']['hashtags']:
            values.append(ht.get('tag'))
        return values

    # these could have a default behavior if not provided.  also they could look thru
    #   *whole* text (word-by-word), not just hashtags
    def derive_taxonomy(self):
        from app.modules.site_settings.models import Taxonomy

        for ht in self.hashtag_values():
            tx = Taxonomy.find_fuzzy(ht)
            log.debug(f'hashtag "{ht}" matched {tx}')
            return tx
        return None

    # this override is only to satisify the deadline hack of not using real user.linked_account process FIXME
    #   remove it (to let baseclass method run) when hack is gone
    def find_author_user(self):
        from app.modules.users.models import User
        from sqlalchemy import func

        username = self.get_author_username()
        if not username:
            log.warning(f'cannot find author user: username not found for {self}')
            return None
        return User.query.filter(
            func.lower(User.twitter_username) == username.lower()
        ).first()
