"""Binary sensor platform for ChirpStack HTTP integration."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.restore_state import RestoreEntity
import logging
from .helpers import device_info, registry_entities


_LOGGER = logging.getLogger(__name__)
DOMAIN = "chirpstack_http"

class ChirpstackBinarySensor(BinarySensorEntity, RestoreEntity):
    """Representation of a ChirpStack binary sensor."""

    def __init__(self, device_id, device_class, name, unique_id, info):
        """Initialize the binary sensor."""
        self._device_id = device_id
        self._attr_name = name
        self._attr_unique_id = unique_id
        if device_class:
            self._attr_device_class = device_class
        self._attr_device_info = device_info(device_id, info)

        _LOGGER.debug(f"Created binary sensor: {name}")

    async def async_added_to_hass(self):
        """Restore the last state when recreated after a restart."""
        await super().async_added_to_hass()
        if self._attr_is_on is not None:
            return
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in ("on", "off"):
            self._attr_is_on = last_state.state == "on"
            _LOGGER.debug(f"Restored state for {self.name}: {last_state.state}")

    def set_initial_value(self, value):
        """Set the value without triggering a state update"""
        _LOGGER.debug(f"Setting initial value for {self.name}: {value}")
        self._attr_is_on = value

    def update_state(self, value):
        """Update the binary sensor state."""
        _LOGGER.debug(f"Updating binary sensor '{self.name}' with value: {value}")
        self._attr_is_on = value

        # If already added to HA, write state
        if hasattr(self, 'hass') and self.hass is not None:
            _LOGGER.debug(f"Writing state for binary sensor {self.name}")
            self.async_write_ha_state()


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the binary sensor platform, recreating sensors known from earlier runs."""
    data = hass.data[DOMAIN][entry.entry_id]
    data["_platform_binary_sensor"] = async_add_entities

    restored = []
    for dev_eui, key, reg, info in registry_entities(hass, entry, "binary_sensor"):
        device_class = BinarySensorDeviceClass(reg.original_device_class) if reg.original_device_class else None
        entity = ChirpstackBinarySensor(dev_eui, device_class, reg.original_name, reg.unique_id, info)
        data["devices"].setdefault(dev_eui, {})[key] = entity
        restored.append(entity)
    _LOGGER.debug(f"Restoring {len(restored)} binary sensors for entry {entry.entry_id}")
    async_add_entities(restored)
