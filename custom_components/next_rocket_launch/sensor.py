"""The Next Rocket Launch integration."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import logging
from typing import Any

import aiohttp
from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.event import Event
from ical.exceptions import CalendarParseError
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util, slugify

_LOGGER = logging.getLogger(__name__)

DOMAIN = "next_rocket_launch"
DEFAULT_NAME = "Next rocket launch"
DEFAULT_ROCKET_NAME = "ALL"
ICS_URL = "https://ics.teamup.com/feed/ks9mo8bt5a2he89r6j/0.ics"
ATTRIBUTION = "Data provided by Teamup"
SCAN_INTERVAL = timedelta(minutes=60)
REQUEST_TIMEOUT = 30

PREVIOUS_LOOKBACK = timedelta(days=365)
FUTURE_HORIZON = timedelta(days=365)

LAUNCH_CATEGORY = "Calendrier NextSpaceFlight"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Optional("rocket_name", default=DEFAULT_ROCKET_NAME): cv.ensure_list}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Create the launch sensor."""
    coordinator = RocketLaunchCoordinator(hass)
    await coordinator.async_refresh()

    async_add_entities(
        NextLaunchSensor(coordinator, option) for option in config["rocket_name"]
    )


def _as_datetime(value: date | datetime | None) -> datetime | None:
    """Normalize an event start to an aware datetime.

    All-day events expose a plain ``date``; anchor those to local midnight so
    they stay comparable with, and publishable as, a timestamp.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return dt_util.as_utc(value)
    return dt_util.start_of_local_day(datetime(value.year, value.month, value.day))


class RocketLaunchCoordinator(DataUpdateCoordinator[Calendar]):
    """Fetch and parse the shared ICS feed once for every sensor."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> Calendar:
        """Get the latest data from ics."""
        _LOGGER.debug("Get the latest data from ics")

        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.get(ICS_URL)
                if resp.status != 200:
                    raise UpdateFailed(
                        f"Unable to get ics file: HTTP {resp.status} ({ICS_URL})"
                    )
                raw_ics_file = await resp.text()
        except TimeoutError as error:
            raise UpdateFailed(f"Timeout getting ics file ({ICS_URL})") from error
        except aiohttp.ClientError as error:
            raise UpdateFailed(
                f"Unable to get ics file: {error} ({ICS_URL})"
            ) from error

        try:
            calendar = await self.hass.async_add_executor_job(
                IcsCalendarStream.calendar_from_ics, raw_ics_file
            )
        except CalendarParseError as error:
            raise UpdateFailed(
                f"Unable to parse ics file: {error} ({ICS_URL})"
            ) from error

        if not any(LAUNCH_CATEGORY in event.categories for event in calendar.events):
            _LOGGER.warning(
                "No event categorized as %r in the feed: the previous launch "
                "will not be reported (%s)",
                LAUNCH_CATEGORY,
                ICS_URL,
            )

        return calendar


class NextLaunchSensor(CoordinatorEntity[RocketLaunchCoordinator], SensorEntity):
    """The class for handling the data."""

    _attr_attribution = ATTRIBUTION
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:rocket"

    def __init__(self, coordinator: RocketLaunchCoordinator, rocket_name: str) -> None:
        """Initialize the sensor object."""
        _LOGGER.debug("Initialize the sensor object")
        super().__init__(coordinator)
        self._rocket_name = rocket_name
        self._attr_name = f"Next Rocket {rocket_name}"
        self._attr_unique_id = f"{DOMAIN}_{slugify(rocket_name)}"
        self._process_calendar()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Process data."""
        self._process_calendar()
        super()._handle_coordinator_update()

    def _matches(self, event: Event) -> bool:
        """Return True if the event belongs to the tracked rocket."""
        if self._rocket_name == DEFAULT_ROCKET_NAME:
            return True
        return self._rocket_name in (event.summary or "")

    @staticmethod
    def _is_launch(event: Event) -> bool:
        """Return True for an actual rocket launch."""
        return LAUNCH_CATEGORY in event.categories

    @callback
    def _process_calendar(self) -> None:
        """Pick the next and previous launch out of the calendar."""
        _LOGGER.debug("Start update for %s", self._attr_name)

        attributes: dict[str, Any] = {}
        native_value: datetime | None = None

        calendar = self.coordinator.data
        if calendar is None:
            _LOGGER.debug("ICS data not init")
            self._attr_native_value = native_value
            self._attr_extra_state_attributes = attributes
            return

        now = dt_util.utcnow()
        horizon = now + FUTURE_HORIZON
        previous_event: Event | None = None
        next_event: Event | None = None
        next_start: datetime | None = None

        for event in calendar.timeline.start_after(now - PREVIOUS_LOOKBACK):
            start = _as_datetime(event.dtstart)
            if start is None:
                continue
            if start > horizon:
                break
            if not self._matches(event):
                continue
            if start < now:
                if self._is_launch(event):
                    previous_event = event
            else:
                next_event = event
                next_start = start
                break

        if next_event is not None:
            native_value = next_start
            attributes["Comment"] = next_event.summary
            attributes["Location"] = next_event.location
            attributes["Url"] = str(next_event.url) if next_event.url else None

        if previous_event is not None:
            attributes["Previous"] = previous_event.summary
            previous_start = _as_datetime(previous_event.dtstart)
            attributes["Previous date"] = (
                previous_start.isoformat() if previous_start else None
            )

        attributes["last_update"] = dt_util.now().isoformat()

        self._attr_native_value = native_value
        self._attr_extra_state_attributes = attributes

        _LOGGER.debug(
            "Update done for %s: %s", self._attr_name, self._attr_native_value
        )
