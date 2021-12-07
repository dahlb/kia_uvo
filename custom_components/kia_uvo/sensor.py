import logging

from homeassistant.const import (
    PERCENTAGE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_MILES,
    TIME_MINUTES,
    TEMP_FAHRENHEIT,
    DEVICE_CLASS_DATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util
from datetime import datetime

from .vehicle import Vehicle
from .kia_uvo_entity import KiaUvoEntity, DeviceInfoMixin
from .const import (
    CONF_VEHICLE_IDENTIFIER,
    DATA_VEHICLE_INSTANCE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES: int = 1


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigType, async_add_entities
):
    vehicle_identifier = config_entry.data[CONF_VEHICLE_IDENTIFIER]
    vehicle: Vehicle = hass.data[DOMAIN][vehicle_identifier][DATA_VEHICLE_INSTANCE]

    instruments = [
        (
            "EV Battery",
            "ev_battery_level",
            PERCENTAGE,
            "mdi:car-electric",
            DEVICE_CLASS_BATTERY,
        ),
        (
            "Range by EV",
            "ev_remaining_range_value",
            LENGTH_MILES,
            "mdi:road-variant",
            None,
        ),
        (
            "Estimated Current Charge Duration",
            "ev_charge_remaining_time",
            TIME_MINUTES,
            "mdi:ev-station",
            None,
        ),
        (
            "Target Capacity of Charge AC",
            "ev_max_ac_charge_level",
            PERCENTAGE,
            "mdi:car-electric",
            None,
        ),
        (
            "Target Capacity of Charge DC",
            "ev_max_dc_charge_level",
            PERCENTAGE,
            "mdi:car-electric",
            None,
        ),
        (
            "Odometer",
            "odometer_value",
            LENGTH_MILES,
            "mdi:speedometer",
            None,
        ),
        (
            "Car Battery",
            "battery_level",
            PERCENTAGE,
            "mdi:car-battery",
            DEVICE_CLASS_BATTERY,
        ),
        (
            "Set Temperature",
            "climate_temperature_value",
            TEMP_FAHRENHEIT,
            None,
            DEVICE_CLASS_TEMPERATURE,
        ),
        (
            "Last Synced To Cloud",
            "last_synced_to_cloud",
            None,
            "mdi:update",
            DEVICE_CLASS_TIMESTAMP,
        ),
        (
            "Sync Age",
            "sync_age",
            TIME_MINUTES,
            "mdi:update",
            DEVICE_CLASS_DATE,
        ),
    ]

    sensors = []

    for description, key, unit, icon, device_class in instruments:
        sensors.append(
            InstrumentSensor(
                vehicle,
                description,
                key,
                unit,
                icon,
                device_class,
            )
        )

    async_add_entities(sensors, True)

    usage_counters = [
        (
            "Action Calls Today",
            "calls_today_for_actions",
        ),
        (
            "Update Calls Today",
            "calls_today_for_update",
        ),
        (
            "Sync Requests Today",
            "calls_today_for_request_sync",
        ),
    ]

    usage_sensors = []

    for description, key in usage_counters:
        sensors.append(
            ApiUsageSensor(
                vehicle,
                description,
                key,
            )
        )

    async_add_entities(usage_sensors, True)


class InstrumentSensor(KiaUvoEntity):
    def __init__(
        self,
        vehicle: Vehicle,
        description,
        key,
        unit,
        icon,
        device_class,
    ):
        super().__init__(vehicle)
        self._attr_unique_id = f"{DOMAIN}-{vehicle.identifier}-{key}"
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_unit_of_measurement = unit
        self._attr_name = f"{vehicle.name} {description}"

        self._key = key

    @property
    def state(self):
        if self._key == "last_synced_to_cloud":
            return dt_util.as_local(self._vehicle.last_synced_to_cloud).isoformat()
        if self._key == "sync_age":
            local_timezone = dt_util.UTC
            age_of_last_sync = (
                datetime.now(local_timezone) - self._vehicle.last_synced_to_cloud
            )
            return int(age_of_last_sync.total_seconds() / 60)

        value = getattr(self._vehicle, self._key)
        return value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        key_to_check = self._key
        if self._key == "sync_age":
            key_to_check = "last_synced_to_cloud"
        return super() and getattr(self._vehicle, key_to_check) is not None


class ApiUsageSensor(DeviceInfoMixin, Entity):
    _attr_should_poll: bool = False
    _attr_icon = "mdi:api"
    _attr_state = 0

    def __init__(
        self,
        vehicle: Vehicle,
        description,
        key,
    ):
        self._vehicle = vehicle
        self._attr_unique_id = f"{DOMAIN}-{vehicle.identifier}-{key}"
        self._attr_name = f"{vehicle.name} {description}"
        self._counter_date = dt_util.as_local(dt_util.utcnow())
        setattr(vehicle, key, self)

    def mark_used(self):
        event_time_local = dt_util.as_local(dt_util.utcnow())
        if dt_util.start_of_local_day(self._counter_date) != dt_util.start_of_local_day(
            event_time_local
        ):
            self._counter_date = event_time_local
            self._attr_state = 0
        self._attr_state += 1
        self.async_write_ha_state()
