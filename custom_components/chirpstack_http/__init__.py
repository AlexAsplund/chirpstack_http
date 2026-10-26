from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import logging
from .http import ChirpstackHttpView
from .helpers import async_send_downlink

_LOGGER = logging.getLogger(__name__)
DOMAIN = "chirpstack_http"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CLIMATE, Platform.SWITCH]

SEND_DOWNLINK_SCHEMA = vol.Schema({
    vol.Required("dev_eui"): cv.string,
    vol.Required("data"): cv.string,
    vol.Optional("fport", default=2): vol.All(vol.Coerce(int), vol.Range(min=1, max=223)),
    vol.Optional("confirmed", default=False): cv.boolean,
})


async def async_setup(hass, config):
    """Set up the ChirpStack HTTP component."""

    async def _send_downlink(call: ServiceCall):
        dev_eui = call.data["dev_eui"].lower()
        try:
            payload = bytes.fromhex(call.data["data"])
        except ValueError as err:
            raise HomeAssistantError(f"data must be hex: {err}") from err
        entries = hass.config_entries.async_entries(DOMAIN)
        # Prefer the entry that has seen this device, else any entry
        entry = next((e for e in entries if dev_eui in hass.data.get(DOMAIN, {}).get(e.entry_id, {}).get("devices", {})), None)
        entry = entry or next(iter(entries), None)
        if entry is None:
            raise HomeAssistantError("No ChirpStack HTTP entry configured")
        await async_send_downlink(hass, entry, dev_eui, payload, call.data["fport"], call.data["confirmed"])

    hass.services.async_register(DOMAIN, "send_downlink", _send_downlink, schema=SEND_DOWNLINK_SCHEMA)
    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    entry_id = config_entry.entry_id
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry_id] = {
        "devices": {},
        "climates": {},
        "switches": {},
    }

    # Platforms first: they recreate known entities from the entity registry,
    # so uplinks arriving afterwards update them instead of creating duplicates
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Views can't be unregistered, so only register once (entry reloads reuse it)
    registered = hass.data.setdefault(f"{DOMAIN}_views", set())
    if entry_id not in registered:
        url_suffix = config_entry.data["url_suffix"]
        header_name = config_entry.data.get("header_name")
        header_value = config_entry.data.get("header_value")
        hass.http.register_view(ChirpstackHttpView(hass, entry_id, url_suffix, header_name, header_value))
        registered.add(entry_id)

    return True
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
