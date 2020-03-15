"""The Next Rocket Launch integration."""

from datetime import datetime, timedelta, timezone
import logging

from ics import Calendar
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DOMAIN = "next_rocket_launch"
DEFAULT_NAME = "Next rocket launch"
DEFAULT_ROCKET_NAME = "ALL"
ICS_URL = "https://ics.teamup.com/feed/ks9mo8bt5a2he89r6j/0.ics"
ATTRIBUTION = "Data provided by Teamup"
SCAN_INTERVAL = timedelta(minutes=60)
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional("rocket_name", default=DEFAULT_ROCKET_NAME): cv.ensure_list}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Create the launch sensor."""
    ics_data_provider = GetICSData(ICS_URL)

    nl_sensors = []
    for option in config.get("rocket_name"):
        _LOGGER.debug("Sensor device - %s", option)
        nl_sensors.append(GetNextLaunch(option, ics_data_provider))

    async_add_entities(nl_sensors, True)


class GetICSData:
    """The class for handling the data retrieval."""

    def __init__(self, url):
        """Initialize the data object."""
        _LOGGER.debug("Initialize the data object")
        self.url = url
        self.timeline = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from ics."""
        _LOGGER.debug("Get the latest data from ics")

        raw_ics_file = requests.get(self.url)

        if raw_ics_file.status_code == 200:
            try:
                parsed_ics = Calendar(requests.get(self.url).text)
                self.timeline = list(parsed_ics.timeline)
            except ValueError as error:
                _LOGGER.error(
                    "Unable (ValueError) to parse ics file: %s (%s)", error, self.url
                )
            except NotImplementedError as error:
                _LOGGER.error(
                    "Unable (NotImplementedError) to parse ics file: %s (%s)",
                    error,
                    self.url,
                )

        else:
            _LOGGER.error(
                "Unable to get ics file: %s (%s)", raw_ics_file.status_code, self.url
            )


class GetNextLaunch(Entity):
    """The class for handling the data."""

    def __init__(self, rocket_name, ics_data_provider):
        """Initialize the sensor object."""
        _LOGGER.debug("Initialize the sensor object")
        self.ics_data_provider = ics_data_provider
        self.rocket_name = rocket_name
        self._name = "Next Rocket " + rocket_name
        self._attributes = {}
        self._state = None
        self.have_futur = False

    async def async_update(self):
        """Process data."""
        _LOGGER.debug("Start async update for %s", self.name)

        self.have_futur = False
        self.ics_data_provider.update()

        if self.ics_data_provider is None:
            return

        last_passed = None
        last_futur = None

        if self.rocket_name == "ALL":
            selected_events = self.ics_data_provider.timeline
        else:
            selected_events = [
                x for x in self.ics_data_provider.timeline if self.rocket_name in x.name
            ]

        for event in selected_events:
            if event.begin < datetime.now(timezone.utc):
                last_passed = event
            else:
                if not self.have_futur:
                    last_futur = event
                    self.have_futur = True

        if last_futur is not None:
            self._state = last_futur.begin.isoformat()
            self._attributes["Comment"] = last_futur.name
            self._attributes["Location"] = last_futur.location
            self._attributes["Url"] = last_futur.url
        else:
            self._state = "Not planned"

        if last_passed is not None:
            self._attributes["Previous"] = last_passed.name
            self._attributes["Previous date"] = last_passed.begin.format()

        self._attributes[ATTR_ATTRIBUTION] = ATTRIBUTION
        self._attributes["last_update"] = datetime.now()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:rocket"

    @property
    def device_state_attributes(self):
        """Return attributes for the sensor."""
        return self._attributes

    @property
    def device_class(self):
        """Return device_class."""
        if self.have_futur:
            return "timestamp"

        return "text"
