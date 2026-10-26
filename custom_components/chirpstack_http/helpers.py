import re
import base64
from homeassistant.const import UnitOfConductivity, UnitOfTemperature, UnitOfElectricPotential
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
import logging


_LOGGER = logging.getLogger(__name__)
DOMAIN = "chirpstack_http"

SENSOR_DETECTION_MAP = [
    [
        r"temp",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS
    ],
    [
        r"humid",
        SensorDeviceClass.HUMIDITY,
        PERCENTAGE
    ],
    [
        r"voltage",
        SensorDeviceClass.VOLTAGE,
        UnitOfElectricPotential.VOLT
    ],
    [
        r"battery",
        SensorDeviceClass.BATTERY,
        PERCENTAGE
    ],
    [
        r"rssi",
        SensorDeviceClass.SIGNAL_STRENGTH,
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    ],
    [
        r"snr",
        SensorDeviceClass.SIGNAL_STRENGTH,
        SIGNAL_STRENGTH_DECIBELS
    ],
    [
        r"( ec | ec$ |electrical.?conductivity)",
        SensorDeviceClass.CONDUCTIVITY,
        UnitOfConductivity.MILLISIEMENS_PER_CM
    ],
]

BINARY_SENSOR_DETECTION_MAP = [
    [
        r"closed|open",
        BinarySensorDeviceClass.DOOR,
    ],
    [
        r"motion",
        BinarySensorDeviceClass.MOTION,
    ],
    [
        r"open",
        BinarySensorDeviceClass.DOOR,
    ],
    [
        r"occupancy",
        BinarySensorDeviceClass.OCCUPANCY,
    ],
    [
        r"presence",
        BinarySensorDeviceClass.PRESENCE,
    ],
    [
        r"tamper",
        BinarySensorDeviceClass.TAMPER,
    ],
    [
        r"water",
        BinarySensorDeviceClass.MOISTURE
    ]
]
    
    
def detect_sensor_unit(*args):
    """Detect unit of measurement based on key name."""
    logging.debug(f"Detecting sensor unit from keys: {args}")
    
    for key in args:
        found_class = None
        found_unit = None
        if key is None:
            continue
        key_l = key.lower()
        key_u = key.upper()
        if "," in key:
            found_class,found_unit = key.split(",")
        if found_class or found_unit:
            
            found_class = found_class.strip()
            found_unit = found_unit.strip()
            if found_class.upper() in SensorDeviceClass.__dict__:
                return [found_unit, SensorDeviceClass.__dict__[found_class]]
            else:
                return [found_unit, None]
            
        for pattern, device_class, unit in SENSOR_DETECTION_MAP:
            if re.search(pattern, key_l):
                _LOGGER.debug(f"Detected sensor unit: {unit} and device class: {device_class} for key: {key}")
                return [unit, device_class]
        
        if key_u in SensorDeviceClass.__dict__:
            return [None, SensorDeviceClass.__dict__[key_u]]
        
        
    return [None,None]

def detect_binary_sensor_device_class(*args):
    """Detect unit of measurement based on key name."""
    for key in args:
        
        if key is None:
            continue
        key_l = key.lower()
        key_u = key.upper()
        
        for pattern, device_class in BINARY_SENSOR_DETECTION_MAP:
            if re.search(pattern, key_l):
                _LOGGER.debug(f"Detected binary sensor device class: {device_class} for key: {key}")
                return device_class
        
        if key_u in BinarySensorDeviceClass.__dict__:
            _LOGGER.debug(f"Detected binary sensor device class: {BinarySensorDeviceClass.__dict__[key_u]} for key: {key}")
            return BinarySensorDeviceClass.__dict__[key_u]
        
    return None


def device_info(device_id, info):
    """Build DeviceInfo from ChirpStack metadata."""
    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=info.get("deviceName", f"Device {device_id}"),
        manufacturer=info.get("tenantName", "ChirpStack"),
        model=info.get("deviceProfileName", "Unknown")
    )


def registry_entities(hass, entry, domain):
    """Yield (dev_eui, key, registry_entry, device_info) for entities created before a restart.

    unique_id is "<devEui>_<key>"; devEui is hex so the first "_" splits it.
    """
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    for reg in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if reg.domain != domain or "_" not in reg.unique_id:
            continue
        dev_eui, key = reg.unique_id.split("_", 1)
        device = dev_reg.async_get(reg.device_id) if reg.device_id else None
        info = {"deviceName": device.name, "tenantName": device.manufacturer, "deviceProfileName": device.model} if device else {}
        yield dev_eui, key, reg, info


async def async_send_downlink(hass, entry, dev_eui, payload, fport=2, confirmed=False):
    """Enqueue a downlink via the ChirpStack REST API (chirpstack-rest-api proxy)."""
    conf = {**entry.data, **entry.options}
    if not conf.get("api_url") or not conf.get("api_token"):
        raise HomeAssistantError("ChirpStack API URL/token not set, configure them in the integration options")
    _LOGGER.debug(f"Sending downlink to {dev_eui} on port {fport}: {payload.hex()}")
    session = async_get_clientsession(hass)
    async with session.post(
        f"{conf['api_url'].rstrip('/')}/api/devices/{dev_eui}/queue",
        headers={"Grpc-Metadata-Authorization": f"Bearer {conf['api_token']}"},
        json={"queueItem": {"devEui": dev_eui, "confirmed": confirmed, "fPort": fport, "data": base64.b64encode(payload).decode()}},
    ) as resp:
        if resp.status != 200:
            raise HomeAssistantError(f"ChirpStack downlink failed ({resp.status}): {await resp.text()}")
