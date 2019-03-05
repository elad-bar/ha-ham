"""
This component provides support for Home Automation Manager (HAM).
For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ham/
"""
import logging
from datetime import datetime, timedelta

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.const import (CONF_NAME, CONF_ENTITY_ID, STATE_OFF, STATE_NOT_HOME, EVENT_STATE_CHANGED,
                                 EVENT_HOMEASSISTANT_START)
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.script import Script

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.input_boolean import DOMAIN as INPUT_BOOLEAN_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.group import DOMAIN as GROUP_DOMAIN

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'ham'
DATA_HAM = 'data_ham'
SIGNAL_UPDATE_HAM = "ham_update"
DEFAULT_NAME = 'Home Automation Manager'

GROUP_TRACKER_ICON = 'mdi:home'

ATTR_WEEKDAY = 'Weekday'
ATTR_DATE = 'Date'
ATTR_PROFILE = 'Profile'
ATTR_PARTS_EVENTS = 'Parts_Events'
ATTR_PARTS = 'Parts'
ATTR_PART = 'Part'
ATTR_EVENTS = 'Overrides of Today'
ATTR_CUSTOM_PROFILES = 'custom_profiles'
ATTR_CONFIG_ERRORS = 'configuration_errors'

DEFAULT_PROFILE = 'Default'
AWAY_PROFILE = 'Away'

DAY_PART_MORNING = 'Morning'
DAY_PART_NOON = 'Noon'
DAY_PART_AFTERNOON = 'Afternoon'
DAY_PART_EVENING = 'Evening'
DAY_PART_NIGHT = 'Night'

DAY_SUNDAY = 'Sunday'
DAY_MONDAY = 'Monday'
DAY_TUESDAY = 'Tuesday'
DAY_WEDNESDAY = 'Wednesday'
DAY_THURSDAY = 'Thursday'
DAY_FRIDAY = 'Friday'
DAY_SATURDAY = 'Saturday'

CONF_PARTS = 'parts'

CONF_PROFILES = 'profiles'
CONF_PROFILE_NAME = 'profile'
CONF_PROFILE_DEFAULT = 'default_profile'
CONF_PROFILE_FROM = 'from'

CONF_EVENTS = 'events'
CONF_EVENT_DATE = 'date'
CONF_EVENT_TIME = 'time'
CONF_EVENT_TITLE = 'title'
CONF_EVENT_DAY = 'day'

CONF_TRACKERS = 'trackers'
CONF_SCENES = 'scenes'
CONF_SCENE_NAME = 'scene'
CONF_SCENE_SCRIPT = 'script'

NOTIFICATION_ID = 'ham_notification'
NOTIFICATION_TITLE = 'Home Automation Manager Setup'

SCAN_INTERVAL = timedelta(seconds=60)

DEPENDENCIES = [DEVICE_TRACKER_DOMAIN, INPUT_BOOLEAN_DOMAIN, SWITCH_DOMAIN]

TRACKERS_AWAY_STATES = [STATE_NOT_HOME, STATE_OFF]
ALLOWED_TRACKERS = [DEVICE_TRACKER_DOMAIN]
SYSTEM_PROFILES = [DEFAULT_PROFILE, AWAY_PROFILE]
DAY_PART_TYPES = [DAY_PART_MORNING, DAY_PART_NOON, DAY_PART_AFTERNOON, DAY_PART_EVENING, DAY_PART_NIGHT]
DAY_NAMES = [DAY_SUNDAY, DAY_MONDAY, DAY_TUESDAY, DAY_WEDNESDAY, DAY_THURSDAY, DAY_FRIDAY, DAY_SATURDAY]
SCENES_TYPES = [DAY_PART_MORNING, DAY_PART_NOON, DAY_PART_AFTERNOON, DAY_PART_EVENING, DAY_PART_NIGHT, AWAY_PROFILE]

SCENE_SCHEMA = vol.Schema({
    vol.Required(CONF_SCENE_NAME):
        vol.In(SCENES_TYPES),
    vol.Required(CONF_SCENE_SCRIPT): cv.SCRIPT_SCHEMA
})

PART_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME):
        vol.In(DAY_PART_TYPES),
    vol.Required(CONF_PROFILE_FROM): cv.string,
})

PARTS_SCHEMA = vol.All(
    cv.ensure_list,
    [vol.Any(PART_SCHEMA)],
)

PROFILE_DEFAULT_SCHEMA = vol.Schema({
    vol.Required(CONF_PARTS): PARTS_SCHEMA
})

PROFILE_SCHEMA = vol.Schema({
    vol.Required(CONF_PROFILE_NAME): cv.string,
    vol.Required(CONF_PARTS):
        vol.All(cv.ensure_list, [vol.Any(PART_SCHEMA)])
})

PROFILE_OVERRIDE_SCHEMA = vol.Schema({
    vol.Required(CONF_PROFILE_NAME): cv.string,
    vol.Required(CONF_EVENT_TITLE): cv.string,
})

PROFILE_DATE_OVERRIDE_SCHEMA = PROFILE_OVERRIDE_SCHEMA.extend({
    vol.Required(CONF_EVENT_DATE): cv.string,
})

PROFILE_DAY_OVERRIDE_SCHEMA = PROFILE_OVERRIDE_SCHEMA.extend({
    vol.Required(CONF_EVENT_DAY):
        vol.In(DAY_NAMES),
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PROFILE_DEFAULT): PROFILE_DEFAULT_SCHEMA,
        vol.Optional(CONF_PROFILES):
            vol.All(cv.ensure_list, [vol.Any(PROFILE_SCHEMA)]),
        vol.Optional(CONF_EVENTS):
            vol.All(cv.ensure_list, [vol.Any(PROFILE_DATE_OVERRIDE_SCHEMA, PROFILE_DAY_OVERRIDE_SCHEMA)]),
        vol.Optional(CONF_TRACKERS): cv.entity_ids,
        vol.Optional(CONF_SCENES):
            vol.All(cv.ensure_list, [vol.Any(SCENE_SCHEMA)]),
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up an Home Automation Manager component."""

    try:
        conf = config[DOMAIN]
        scan_interval = SCAN_INTERVAL
        default_profile = conf.get(CONF_PROFILE_DEFAULT)
        profiles = conf.get(CONF_PROFILES)
        events = conf.get(CONF_EVENTS)
        trackers = conf.get(CONF_TRACKERS)
        scenes = conf.get(CONF_SCENES)
        default_profile_parts = default_profile[CONF_PARTS]

        ham_configuration_transformer = HomeAutomationManagerConfigurationTransformer(default_profile_parts, profiles,
                                                                                      events, trackers, scenes)
        configuration = ham_configuration_transformer.get_configuration()

        ham_data = HomeAutomationManagerData(hass, scan_interval, configuration)

        was_initialized = ham_data.was_initialized()

        if was_initialized:
            hass.data[DATA_HAM] = ham_data

        return was_initialized

    except Exception as ex:
        _LOGGER.error('Error while initializing HAM, exception: {}'.format(str(ex)))

        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)

        return False


class HomeAutomationManagerConfigurationTransformer:
    def __init__(self, default_profile_parts, profiles, events, trackers, scenes):
        self._raw_default_profile_parts = default_profile_parts
        self._raw_profiles = profiles
        self._raw_events = events
        self._raw_scenes = scenes

        self._trackers = trackers
        self._profiles = {}
        self._scenes = {}
        self._events = {}
        self._custom_profiles = []
        self._configuration = {}
        self._configuration_errors = None

        self.build_configuration()

    def build_configuration(self):
        self.transform_profiles()
        self.transform_events()
        self.transform_scenes()

        self._configuration = {
            CONF_PROFILES: self._profiles,
            CONF_TRACKERS: self._trackers,
            CONF_SCENES: self._scenes,
            CONF_EVENTS: self._events,
            ATTR_CONFIG_ERRORS: self._configuration_errors,
            ATTR_CUSTOM_PROFILES: self._custom_profiles
        }

    def get_configuration(self):
        return self._configuration

    def log_warn(self, message):
        if self._configuration_errors is None:
            self._configuration_errors = []

        self._configuration_errors.append('WARN - {}'.format(message))
        _LOGGER.warning(message)

    def log_error(self, message):
        if self._configuration_errors is None:
            self._configuration_errors = []

        self._configuration_errors.append('ERROR - {}'.format(message))
        _LOGGER.error(message)

    def transform_profiles(self):
        try:
            if DEFAULT_PROFILE in self._raw_profiles:
                self.log_warn('{} profile is system profile'.format(DEFAULT_PROFILE))

            elif AWAY_PROFILE in self._raw_profiles:
                self.log_warn('{} profile is system profile'.format(AWAY_PROFILE))

            else:
                self.add_default_profiles()

                for profile in self._raw_profiles:
                    profile_name = profile[CONF_PROFILE_NAME]
                    parts = None

                    if CONF_PARTS in profile:
                        profile_parts = profile[CONF_PARTS]

                        parts = self.transform_profile_parts(profile_name, profile_parts)

                    self._profiles[profile_name] = {
                        CONF_PARTS: parts,
                        CONF_EVENTS: {}
                    }

                    if profile_name not in SYSTEM_PROFILES:
                        self._custom_profiles.append(profile_name)

        except Exception as ex:
            self.log_error("transform_profiles failed due to the following exception: {}".format(str(ex)))

    def transform_profile_parts(self, profile_name, profile_parts):
        transformed_parts = {}

        try:
            if profile_parts is not None:
                for profile_part in profile_parts:
                    part_name = profile_part[CONF_NAME]
                    part_from = profile_part[CONF_PROFILE_FROM]

                    if part_name in transformed_parts:
                        self.log_warn('{} already contains part {}'.format(profile_name, part_name))
                    else:
                        _LOGGER.info(
                            'Set part {} for profile {} starting at: {}'.format(profile_name, part_name, part_from))

                        transformed_parts[part_name] = part_from
        except Exception as ex:
            self.log_error("transform_profile_parts failed due to the following exception: {}".format(str(ex)))

        return transformed_parts

    def transform_events(self):
        try:
            for event in self._raw_events:
                event_title = event[CONF_EVENT_TITLE]
                event_profile = event[CONF_PROFILE_NAME]
                event_date = None
                event_day = None

                if event_profile not in self._profiles:
                    self.log_warn(
                        'Cannot add event {} since profile {} is undefined'.format(event_title, event_profile))
                elif event_profile in SYSTEM_PROFILES:
                    self.log_warn(
                        'Cannot add event {} since profile {} is system profile'.format(event_title, event_profile))
                else:
                    event_date_time_key = None

                    if CONF_EVENT_DATE in event:
                        event_date = event[CONF_EVENT_DATE]
                        event_date_time_key = event_date

                    if CONF_EVENT_DAY in event:
                        event_day = event[CONF_EVENT_DAY]
                        event_date_time_key = event_day

                    event_id = '{}.{}.{}'.format(event_profile, event_title, event_date_time_key)

                    events = self._profiles[event_profile][CONF_EVENTS]

                    _LOGGER.info(
                        'Adding event {} at {} for profile {}'.format(event_title, event_date_time_key, event_profile))

                    if event_date_time_key in self._events:
                        self._events[event_date_time_key].append({
                            CONF_PROFILE_NAME: event_profile,
                            CONF_EVENT_TITLE: event_title
                        })
                    else:
                        self._events[event_date_time_key] = [{
                            CONF_PROFILE_NAME: event_profile,
                            CONF_EVENT_TITLE: event_title
                        }]

                    if event_id in events:
                        self.log_warn('{} already contains event {}'.format(event_profile, event_title))
                    else:
                        _LOGGER.info('Set event {} for profile {}'.format(event_profile, event_title))

                        events[event_id] = {
                            CONF_EVENT_DAY: event_day,
                            CONF_EVENT_DATE: event_date,
                            CONF_EVENT_TITLE: event_title
                        }
        except Exception as ex:
            self.log_error("transform_events failed due to the following exception: {}".format(str(ex)))

    def transform_scenes(self):
        try:
            for scene in self._raw_scenes:
                scene_name = scene[CONF_SCENE_NAME]
                scene_scripts = scene[CONF_SCENE_SCRIPT]

                if scene_name not in SCENES_TYPES:
                    self.log_warn('Scene {} is not invalid'.format(scene_name))
                else:
                    _LOGGER.info('Set scene {}'.format(scene_name))

                    self._scenes[scene_name] = {
                        CONF_SCENE_NAME: scene_name,
                        CONF_SCENE_SCRIPT: scene_scripts
                    }
        except Exception as ex:
            self.log_error("transform_scenes failed due to the following exception: {}".format(str(ex)))

    @staticmethod
    def get_key(prefix, suffix):
        key = '{}.{}'.format(prefix, suffix)

        return key

    def add_default_profiles(self):
        default_profile = {
            CONF_PROFILE_NAME: DEFAULT_PROFILE,
            CONF_PARTS: self._raw_default_profile_parts
        }

        away_profile = {
            CONF_PROFILE_NAME: AWAY_PROFILE
        }

        self._raw_profiles.append(default_profile)
        self._raw_profiles.append(away_profile)


class HomeAutomationManagerData:
    """The Class for handling the data retrieval."""

    def __init__(self, hass, scan_interval, configuration):
        """Initialize the data object."""
        _LOGGER.debug("HomeAutomationManagerData initialization with following configuration: {}".format(configuration))

        self._profiles = configuration[CONF_PROFILES]
        self._events = configuration[CONF_EVENTS]
        self._trackers = configuration[CONF_TRACKERS]
        self._scenes = configuration[CONF_SCENES]
        self._custom_profiles = configuration[ATTR_CUSTOM_PROFILES]
        self._configuration_errors = configuration[ATTR_CONFIG_ERRORS]

        self._hass = hass
        self._was_initialized = False

        if self._configuration_errors is not None:
            self.create_persistent_notification('<b>Errors while loading configuration:</b><br /> {}'.format(
                '<br /> - '.join(self._configuration_errors)))
            return

        validations = [self.validate_scenes, self.validate_trackers]
        is_valid = True

        for validation in validations:
            if not validation():
                is_valid = False

        if is_valid:
            self._current_scene = None
            self._events_of_today = None
            self._latest_details = None
            self._current_date_time = None
            self._current_weekday = None
            self._current_part = None
            self._current_profile = None
            self._profile_data = None
            self._is_away = None
            self._group_trackers_id = None

            self.create_tracker_group()
            self.initialize_profile_data()

            def ham_refresh(event_time):
                """Call Home Automation Manager (HAM) to refresh information."""
                _LOGGER.debug('Updating Home Automation Manager (HAM) component, at {}'.format(event_time))
                self.update()
                dispatcher_send(hass, SIGNAL_UPDATE_HAM)

            def ham_run_current_scene(event_time):
                """Call Home Automation Manager (HAM) to run current scene."""
                _LOGGER.debug('Calling current scene script, at {}'.format(event_time))
                self.invoke_current_scene()

            self._ham_run_current_scene = ham_run_current_scene
            self._ham_refresh = ham_refresh

            def check_event(event):
                if event.data[CONF_ENTITY_ID] == self._group_trackers_id:
                    time_fired = event.time_fired

                    self._ham_refresh(time_fired)

            # register service
            hass.services.register(DOMAIN, 'update', ham_refresh)
            hass.services.register(DOMAIN, 'run_current_scene', ham_run_current_scene)

            # register scan interval for Home Automation Manager (HAM)
            track_time_interval(hass, ham_refresh, scan_interval)

            hass.bus.listen_once(EVENT_HOMEASSISTANT_START, ham_refresh)

            hass.bus.listen(EVENT_STATE_CHANGED, check_event)

            self._was_initialized = True

    def was_initialized(self):
        return self._was_initialized

    def create_persistent_notification(self, message):
        self._hass.components.persistent_notification.create(
            message,
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)

    def validate_scenes(self):
        if self._scenes is not None:
            for scene_key in self._scenes:
                scene = self._scenes[scene_key]
                scene_name = scene[CONF_SCENE_NAME]
                scripts = scene[CONF_SCENE_SCRIPT]

                _LOGGER.debug("Validate Scene {} - scripts: {}".format(scene_name, scripts))

        return True

    def validate_trackers(self):
        if self._trackers is not None:
            for tracker in self._trackers:
                _LOGGER.debug("Validate Tracker {}".format(tracker))

                current_tracker_domain = tracker.split('.')[0]

                if current_tracker_domain not in ALLOWED_TRACKERS:
                    self.create_persistent_notification('{} is not supported tracker by HAM'.format(tracker))

                    return False

        return True

    def create_tracker_group(self):
        group_trackers_id = "{}_trackers".format(DOMAIN)

        self._group_trackers_id = '{}.{}'.format(GROUP_DOMAIN, group_trackers_id)

        set_group_service = 'set'

        group_data = {
            'object_id': group_trackers_id,
            'icon': GROUP_TRACKER_ICON,
            'visible': True,
            'name': '{} Trackers'.format(DOMAIN.upper()),
            'entities': self._trackers
        }

        self._hass.services.call(GROUP_DOMAIN, set_group_service, group_data, False)

    def get_current_date_time(self):
        return self._current_date_time

    def update_current_date_time(self):
        _LOGGER.debug("update_current_date_time - Start")

        self._current_date_time = datetime.now()

        _LOGGER.debug(
            "update_current_date_time - Completed, Current date and time is {}".format(self._current_date_time))

    def get_weekday(self):
        return self._current_weekday

    def update_weekday(self):
        _LOGGER.debug("update_weekday - Start")

        self._current_weekday = self._current_date_time.strftime('%A')

        _LOGGER.debug("update_weekday - Completed, today is {}".format(self._current_date_time))

    def get_day_part(self):
        return self._current_part

    def update_day_part(self):
        try:
            _LOGGER.debug("update_day_part - Start")

            current_time = self._current_date_time.time()
            current_profile_name = self.get_current_profile()

            if current_profile_name not in self._profiles:
                _LOGGER.warning('update_day_part - failed to find profile {} in profiles'.format(current_profile_name))
            else:
                current_profile = self._profiles[current_profile_name]
                parts = current_profile[CONF_PARTS]

                _LOGGER.debug("update_day_part - Available Parts in {} JSON: {}".format(current_profile_name, parts))

                self._current_part = DAY_PART_TYPES[len(DAY_PART_TYPES) - 1]

                if parts is not None:
                    for part_name in parts:
                        part_from = parts[part_name]

                        part_from_time = datetime.strptime(part_from, "%H:%M:%S").time()

                        _LOGGER.debug(
                            "update_day_part - Checking {} with from time {} comparing {}".format(part_name,
                                                                                                  part_from_time,
                                                                                                  current_time))

                        if current_time >= part_from_time:
                            self._current_part = part_name

                _LOGGER.debug("update_day_part - Completed, Current day part is {}".format(self._current_part))
        except Exception as ex:
            _LOGGER.error("updateDayPart - Exception {}".format(str(ex)))

    def get_events_of_today(self):
        return self._events_of_today

    def get_events_of_today_titles(self):
        title = None
        try:
            titles = []

            if self._events_of_today is not None:
                for event in self._events_of_today:
                    titles.append('{} ({})'.format(event[CONF_EVENT_TITLE], event[CONF_PROFILE_NAME]))

            title = ', '.join(titles)
        except Exception as ex:
            _LOGGER.error("getEventsOfTodayTitles - Exception {}".format(str(ex)))

        return title

    def update_events_of_today(self):
        try:

            events = self._events

            if events is None:
                _LOGGER.debug("update_events_of_today - No overrides available")

                return
            else:
                _LOGGER.debug("update_events_of_today - Start, Available overrides are: {}".format(events))

            self._events_of_today = []

            current_date = self._current_date_time.today().strftime('%Y-%m-%d')
            _LOGGER.debug("update_events_of_today - Today is {}".format(current_date))

            current_day_name = self.get_weekday()

            for main_event_key in events:
                main_event = events[main_event_key]
                for event in main_event:
                    event_profile = event[CONF_PROFILE_NAME]
                    event_title = event[CONF_EVENT_TITLE]

                    if main_event_key in [current_day_name, current_date]:
                        _LOGGER.debug(
                            'update_events_of_today - Event {} profile {} is from today ({})'.format(event_title,
                                                                                                     event_profile,
                                                                                                     main_event_key))
                        self._events_of_today.append(event)
                    else:
                        _LOGGER.debug(
                            "update_events_of_today - Event {} for profile {} is not from today ({})".format(
                                event_title,
                                event_profile,
                                main_event_key))

            _LOGGER.debug("update_events_of_today - Completed")
        except Exception as ex:
            _LOGGER.error("update_events_of_today - Exception {}".format(str(ex)))

    def get_current_scene(self):
        return self._current_scene

    def update_current_scene(self):
        is_away = self.get_is_away()
        current_scene = self.get_day_part()

        if is_away:
            current_scene = AWAY_PROFILE

        self._current_scene = current_scene

    def get_profile_data(self, profile):
        profile_data_all = {}

        if self._profile_data is not None and profile in self._profile_data:
            profile_data = self._profile_data[profile]

            if ATTR_PARTS_EVENTS in profile_data:
                profile_data_all = profile_data[ATTR_PARTS_EVENTS]

        return profile_data_all

    def get_current_profile_data_parts(self):
        profile = self.get_current_profile()

        profile_data_parts = {}

        if self._profile_data is not None and profile in self._profile_data:
            profile_data = self._profile_data[profile]
            if ATTR_PARTS in profile_data:
                profile_data_parts = profile_data[ATTR_PARTS]

        return profile_data_parts

    def initialize_profile_data(self):
        self._profile_data = {}

        all_profiles = self.get_profiles()

        _LOGGER.debug('Loading HAM Binary Sensors')

        for profile_name in all_profiles:
            profile = all_profiles[profile_name]
            parts = None
            events = None

            self._profile_data[profile_name] = {
                ATTR_PARTS_EVENTS: {},
                ATTR_PARTS: {}
            }

            profile_data_all = self._profile_data[profile_name][ATTR_PARTS_EVENTS]
            profile_data_parts = self._profile_data[profile_name][ATTR_PARTS]

            if CONF_PARTS in profile:
                parts = profile[CONF_PARTS]

            if CONF_EVENTS in profile:
                events = profile[CONF_EVENTS]

            if parts is not None:
                for part_name in parts:
                    value = parts[part_name]

                    profile_data_all[part_name] = value
                    profile_data_parts[part_name] = value

            if events is not None:
                for event_id in events:
                    event = events[event_id]
                    event_title = event[CONF_EVENT_TITLE]
                    event_id_arr = event_id.split('.')
                    event_date = event_id_arr[len(event_id_arr) - 1]

                    profile_data_all[event_title] = event_date

    def get_current_profile(self):
        return self._current_profile

    def update_current_profile(self):
        try:
            _LOGGER.debug("update_current_profile - Start")

            self._current_profile = DEFAULT_PROFILE
            events = self.get_events_of_today()

            if events is not None:
                for event in events:
                    event_profile = event[CONF_PROFILE_NAME]

                    if self._current_profile != self._custom_profiles[len(self._custom_profiles) - 1]:
                        self._current_profile = event_profile

            _LOGGER.debug("update_current_profile - Completed, Profile of today is {}".format(self._current_profile))
        except Exception as ex:
            _LOGGER.error("update_current_profile - Exception {}".format(str(ex)))

    def get_details(self):
        return self._latest_details

    def get_profiles(self):
        return self._profiles

    def get_is_away(self):
        return self._is_away

    def update_is_away(self):
        try:
            _LOGGER.debug("update_is_away - Start")

            group_tracker_state = self._hass.states.get(self._group_trackers_id).state

            self._is_away = group_tracker_state in TRACKERS_AWAY_STATES

            _LOGGER.debug("update_is_away - Completed, Away state is {}".format(self._is_away))
        except Exception as ex:
            _LOGGER.error("update_is_away - Exception {}".format(str(ex)))

    def invoke_current_scene(self):
        current_scene = self.get_current_scene()

        _LOGGER.debug("Invoking script of {}".format(current_scene))

        if self._scenes is not None and current_scene in self._scenes:
            scene = self._scenes[current_scene]
            scene_script = scene[CONF_SCENE_SCRIPT]

            script_invoker = Script(self._hass, scene_script)
            script_invoker.run()

    def update(self):
        _LOGGER.debug("update - Start")

        current_scene = self.get_current_scene()

        self.update_current_date_time()
        self.update_weekday()
        self.update_events_of_today()
        self.update_is_away()
        self.update_current_profile()
        self.update_day_part()
        self.update_current_scene()

        if current_scene is not None and current_scene != self.get_current_scene():
            self.invoke_current_scene()

        _LOGGER.debug("update - Completed")
