"""Sensor platform for the ChirpStack HTTP integration."""
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass
import re
import logging
from .helpers import device_info, registry_entities

_LOGGER = logging.getLogger(__name__)
DOMAIN = "chirpstack_http"

# Simplified sensor class
class ChirpstackSensor(RestoreSensor):
    """Representation of a ChirpStack sensor."""

    def __init__(self, device_id, name, device_class, unit, unique_id, info):
        """Initialize the sensor."""
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_device_info = device_info(device_id, info)

        # Debug logging
        _LOGGER.debug(f"Created sensor: {name} with unit {unit}")

    def set_initial_value(self, value):
        """Set the value without triggering a state update"""
        _LOGGER.debug(f"Setting initial value for {self.name}: {value} {self._attr_native_unit_of_measurement}")
        self._attr_native_value = self.sanitize_value(value)

    def sanitize_value(self, value):
        """Sanitize the value based on its type."""
        if isinstance(value, str):
            # Attempt to convert to float if it's a numeric string
            if re.match(r"^\d+(\.\d+)?$", value):
                return float(value)
        return value

    def update_state(self, value):
        """Update the sensor state."""
        _LOGGER.debug(f"Updating sensor '{self.name}' with value: {value} ({type(value).__name__})")
        self._attr_native_value = self.sanitize_value(value)

        # If already added to HA, write state
        if hasattr(self, 'hass') and self.hass is not None:
            _LOGGER.debug(f"Writing state for {self.name}")
            self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Restore the last value when recreated after a restart."""
        await super().async_added_to_hass()
        if self._attr_native_value is None and (last := await self.async_get_last_sensor_data()):
            self._attr_native_value = last.native_value
            _LOGGER.debug(f"Restored state for {self.name}: {last.native_value}")

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform, recreating sensors known from earlier runs."""
    data = hass.data[DOMAIN][entry.entry_id]
    data["_platform_sensor"] = async_add_entities

    restored = []
    for dev_eui, key, reg, info in registry_entities(hass, entry, "sensor"):
        device_class = SensorDeviceClass(reg.original_device_class) if reg.original_device_class else None
        entity = ChirpstackSensor(dev_eui, reg.original_name, device_class, reg.unit_of_measurement, reg.unique_id, info)
        data["devices"].setdefault(dev_eui, {})[key] = entity
        restored.append(entity)
    _LOGGER.debug(f"Restoring {len(restored)} sensors for entry {entry.entry_id}")
    async_add_entities(restored)
