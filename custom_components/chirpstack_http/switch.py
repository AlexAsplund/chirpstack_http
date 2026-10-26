"""Switch platform: MClimate Vicki child lock."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity
from .climate import PENDING_UPLINKS
from .helpers import async_send_downlink, device_info, registry_entities

DOMAIN = "chirpstack_http"


class ChirpstackVickiChildLock(SwitchEntity, RestoreEntity):
    """Child lock: blocks changing the setpoint by turning the Vicki ring."""

    _attr_icon = "mdi:lock"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry, device_id, info):
        self._entry = entry
        self._device_id = device_id
        self._attr_name = f"{info.get('deviceName', f'Device {device_id}')} Child Lock"
        self._attr_unique_id = f"{device_id}_child_lock_switch"
        self._attr_device_info = device_info(device_id, info)
        self._pending = None
        self._pending_uplinks = 0

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if self._attr_is_on is None and (last := await self.async_get_last_state()) and last.state in ("on", "off"):
            self._attr_is_on = last.state == "on"

    def update_from_uplink(self, flat_data):
        reported = flat_data.get("childLock")
        if reported is None:
            return
        if self._pending is not None:
            # Class A: the uplink that fetches our downlink still reports the old value
            self._pending_uplinks += 1
            if reported != self._pending and self._pending_uplinks <= PENDING_UPLINKS:
                return
            self._pending = None
        self._attr_is_on = reported
        if self.hass is not None:
            self.async_write_ha_state()

    async def _set(self, on):
        await async_send_downlink(self.hass, self._entry, self._device_id, bytes([0x07, int(on)]))
        self._pending = on
        self._pending_uplinks = 0
        self._attr_is_on = on
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        await self._set(True)

    async def async_turn_off(self, **kwargs):
        await self._set(False)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the switch platform, recreating switches known from earlier runs."""
    data = hass.data[DOMAIN][entry.entry_id]
    data["_platform_switch"] = async_add_entities

    restored = []
    for dev_eui, _key, _reg, info in registry_entities(hass, entry, "switch"):
        entity = ChirpstackVickiChildLock(entry, dev_eui, info)
        data["switches"][dev_eui] = entity
        restored.append(entity)
    async_add_entities(restored)
