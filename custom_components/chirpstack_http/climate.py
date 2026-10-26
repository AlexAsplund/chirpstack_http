"""Climate platform for MClimate Vicki TRVs behind ChirpStack."""
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.restore_state import RestoreEntity
import logging
from .helpers import async_send_downlink, device_info, registry_entities

_LOGGER = logging.getLogger(__name__)
DOMAIN = "chirpstack_http"

# Keys in the decoded Vicki keepalive that identify the device
VICKI_KEYS = {"targetTemperature", "sensorTemperature", "motorPosition"}
# Uplinks to wait for the device to confirm a new setpoint before trusting what it reports.
# Vicki is class A: the downlink is delivered after the next uplink, which still carries the old value.
PENDING_UPLINKS = 2


def is_vicki(flat_data):
    return VICKI_KEYS <= flat_data.keys()


def vicki_setpoint_payload(temperature):
    """0x0E = whole degrees (fw >= 3.5), 0x51 = tenths as uint16 (fw >= 4.3)."""
    if float(temperature).is_integer():
        return bytes([0x0E, int(temperature)])
    return bytes([0x51]) + round(temperature * 10).to_bytes(2, "big")


class ChirpstackVickiClimate(ClimateEntity, RestoreEntity):
    """MClimate Vicki radiator thermostat."""

    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 5
    _attr_max_temp = 30

    def __init__(self, entry, device_id, info):
        self._entry = entry
        self._device_id = device_id
        self._attr_name = info.get("deviceName", f"Device {device_id}")
        self._attr_unique_id = f"{device_id}_climate"
        self._attr_device_info = device_info(device_id, info)
        self._pending = None
        self._pending_uplinks = 0

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if self._attr_target_temperature is None and (last := await self.async_get_last_state()):
            self._attr_target_temperature = last.attributes.get(ATTR_TEMPERATURE)
            self._attr_current_temperature = last.attributes.get("current_temperature")
            self._attr_current_humidity = last.attributes.get("current_humidity")

    def update_from_uplink(self, flat_data):
        """Update from a decoded Vicki uplink."""
        self._attr_current_temperature = flat_data.get("sensorTemperature", self._attr_current_temperature)
        self._attr_current_humidity = flat_data.get("relativeHumidity", self._attr_current_humidity)
        if "motorOpenness" in flat_data:
            self._attr_hvac_action = HVACAction.HEATING if flat_data["motorOpenness"] > 0 else HVACAction.IDLE

        target = flat_data.get("targetTemperatureFloat", flat_data.get("targetTemperature"))
        if self._pending is not None and target is not None:
            self._pending_uplinks += 1
            if target == self._pending or self._pending_uplinks > PENDING_UPLINKS:
                self._pending = None
            else:
                target = None  # keep showing the requested setpoint until the device applies it
        if target is not None:
            self._attr_target_temperature = target

        if self.hass is not None:
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        temperature = kwargs[ATTR_TEMPERATURE]
        await async_send_downlink(self.hass, self._entry, self._device_id, vicki_setpoint_payload(temperature))
        self._pending = temperature
        self._pending_uplinks = 0
        self._attr_target_temperature = temperature
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        return {"pending_target_temperature": self._pending}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the climate platform, recreating thermostats known from earlier runs."""
    data = hass.data[DOMAIN][entry.entry_id]
    data["_platform_climate"] = async_add_entities

    restored = []
    for dev_eui, _key, _reg, info in registry_entities(hass, entry, "climate"):
        entity = ChirpstackVickiClimate(entry, dev_eui, info)
        data["climates"][dev_eui] = entity
        restored.append(entity)
    async_add_entities(restored)


if __name__ == "__main__":  # cd custom_components && python -m chirpstack_http.climate
    assert vicki_setpoint_payload(24).hex() == "0e18"  # matches MClimate docs example
    assert vicki_setpoint_payload(25.8).hex() == "510102"  # matches MClimate docs example
    assert vicki_setpoint_payload(21.5).hex() == "5100d7"
    print("ok")
