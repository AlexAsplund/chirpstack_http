"""HTTP component for ChirpStack integration."""
import logging
import json
import re
from homeassistant.components.http import HomeAssistantView
from .sensor import ChirpstackSensor
from .binary_sensor import ChirpstackBinarySensor
from .climate import ChirpstackVickiClimate, is_vicki
from .switch import ChirpstackVickiChildLock
from .helpers import detect_sensor_unit, detect_binary_sensor_device_class
DOMAIN = "chirpstack_http"
_LOGGER = logging.getLogger(__name__)


def flatten_dict(d, parent_key='', sep='_'):
    """Flatten a nested dictionary."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def sanitize_value(value, key=None):
    """Convert value to proper type and format."""
    if isinstance(value, bool):
        # Already boolean
        return value
    
    # Check for string booleans
    if isinstance(value, str):
        if value.lower() in ['true', '1', 'yes', 'y', 'on']:
            return True
        elif value.lower() in ['false', '0', 'no', 'n', 'off']:
            return False
    
    # Handle numeric values
    if isinstance(value, (int, float)):
        # Already numeric
        return value
    
    if isinstance(value, str):
        # Try to convert to number
        try:
            # Try integer first
            if value.isdigit():
                return int(value)
            # Try float next
            return float(value)
        except (ValueError, TypeError):
            # Keep as string
            pass
    
    # Return as-is for other types
    return value


class ChirpstackHttpView(HomeAssistantView):
    """View to handle ChirpStack webhook requests."""
    
    def __init__(self, hass, entry_id, url_suffix, header_name=None, header_value=None):
        """Initialize the webhook view."""
        self.hass = hass
        self.entry_id = entry_id
        self.url = f"/api/chirpstack_http/{url_suffix}"
        self.name = f"api:chirpstack_http:{url_suffix}"
        self.requires_auth = False
        self.header_name = header_name
        self.header_value = header_value
    
    async def post(self, request):
        """Handle POST requests for ChirpStack uplinks."""
        try:
            # Check for authentication header if configured
            if self.header_name and self.header_value:
                if self.header_name not in request.headers:
                    _LOGGER.warning(f"Missing authentication header: {self.header_name}")
                    return self.json({"status": "error", "message": "Unauthorized"}, status_code=401)
                
                if request.headers.get(self.header_name) != self.header_value:
                    _LOGGER.warning(f"Invalid authentication header value for: {self.header_name}")
                    return self.json({"status": "error", "message": "Unauthorized"}, status_code=401)
            
            # Parse the JSON data
            data = await request.json()
            _LOGGER.debug(f"Received webhook data: {json.dumps(data)}...")
            
            # Extract device info
            if "deviceInfo" not in data:
                return self.json({"status": "error", "message": "No deviceInfo in payload"})
            
            device_info_raw = data["deviceInfo"]
            dev_eui = device_info_raw.get("devEui")
            
            if not dev_eui:
                return self.json({"status": "error", "message": "No devEui in deviceInfo"})
            
            # Extract object data (sensor readings)
            object_data = data.get("object", {})
            if not object_data or not isinstance(object_data, dict):
                return self.json({"status": "ignored", "message": "No valid object data"})
            
            # Flatten the object data
            flat_data = flatten_dict(object_data)
            
            # Get device metadata
            rx_info = data.get("rxInfo", [{}])[0]
            device_info = {
                "deviceName": device_info_raw.get("deviceName", f"Device {dev_eui}"),
                "tenantName": device_info_raw.get("tenantName", "ChirpStack"),
                "deviceProfileName": device_info_raw.get("deviceProfileName", "Unknown"),
                "gatewayId": rx_info.get("gatewayId", "unknown")
            }
            
            # Initialize device dictionary if needed
            device_id = dev_eui
            hass_data = self.hass.data[DOMAIN][self.entry_id]
            hass_data["devices"].setdefault(device_id, {})
            
            # Track new entities
            new_sensors = []
            new_binary_sensors = []
            
            # Process each data point
            for key, raw_value in flat_data.items():
                _LOGGER.debug(f"Processing data point: {key} = {raw_value} ({type(raw_value).__name__})")
                
                # Generate unique ID and friendly name
                unique_id = f"{device_id}_{key}"
                name_suffix = ' '.join(list(map(lambda x: x.capitalize(), key.replace("_", " ").split(" "))))
                name = f"{device_info['deviceName']} {name_suffix}"
                
                # Sanitize the value
                sanitized_value = sanitize_value(raw_value, key)
                _LOGGER.debug(f"Sanitized value: {sanitized_value} ({type(sanitized_value).__name__})")
                
                # Check if entity already exists
                if key in hass_data["devices"].get(device_id, {}):
                    # Update existing entity
                    _LOGGER.debug(f"Updating existing entity: {name}")
                    entity = hass_data["devices"][device_id][key]
                    entity.update_state(sanitized_value)
                    continue
                
                detection_keys = [object_data.get("type_ref", {}).get(key, None), key]
                
                # Determine if boolean or sensor
                if isinstance(sanitized_value, bool):
                    # Create binary sensor
                    device_class = detect_binary_sensor_device_class(*detection_keys)
                    _LOGGER.info(f"Creating binary sensor: {name} = {sanitized_value}")
                    entity = ChirpstackBinarySensor(device_id,  device_class, name, unique_id, device_info)
                    new_binary_sensors.append(entity)
                else:
                    # Create sensor with appropriate unit
                    unit, device_class = detect_sensor_unit(*detection_keys)
                    _LOGGER.info(f"Creating sensor: {name} = {sanitized_value} {unit}")
                    entity = ChirpstackSensor(device_id, name, device_class, unit, unique_id, device_info)
                    new_sensors.append(entity)
                
                # Store in devices dict
                hass_data["devices"].setdefault(device_id, {})[key] = entity
                entity.set_initial_value(sanitized_value)
            
            # Platforms are set up before the view is registered, so add directly
            if new_sensors:
                _LOGGER.info(f"Adding {len(new_sensors)} sensors to Home Assistant")
                hass_data["_platform_sensor"](new_sensors)
            if new_binary_sensors:
                _LOGGER.info(f"Adding {len(new_binary_sensors)} binary sensors to Home Assistant")
                hass_data["_platform_binary_sensor"](new_binary_sensors)

            # Thermostat + child lock entities for MClimate Vicki
            for store, cls, platform in (
                ("climates", ChirpstackVickiClimate, "_platform_climate"),
                ("switches", ChirpstackVickiChildLock, "_platform_switch"),
            ):
                entity = hass_data[store].get(device_id)
                if entity is None and is_vicki(flat_data):
                    entry = self.hass.config_entries.async_get_entry(self.entry_id)
                    entity = hass_data[store][device_id] = cls(entry, device_id, device_info)
                    _LOGGER.info(f"Adding {platform[10:]} entity for {device_info['deviceName']}")
                    hass_data[platform]([entity])
                if entity is not None:
                    entity.update_from_uplink(flat_data)

            # Return success
            return self.json({
                "status": "ok",
                "device": device_info["deviceName"],
                "sensors_added": len(new_sensors),
                "binary_sensors_added": len(new_binary_sensors)
            })
            
        except Exception as e:
            _LOGGER.exception(f"Error processing webhook: {e}")
            return self.json({
                "status": "error",
                "message": f"Internal error: {str(e)}"
            }, status_code=500)