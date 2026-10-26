from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol

DOMAIN = "chirpstack_http"

class ChirpstackHttpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ChirpstackHttpOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            url_suffix = user_input.get("url_suffix", "chirpstack")
            header_name = user_input.get("header_name", "")
            header_value = user_input.get("header_value", "")

            # Create entry with user input data
            return self.async_create_entry(
                title=f"/api/chirpstack_http/{url_suffix}",
                data={
                    "url_suffix": url_suffix,
                    "header_name": header_name,
                    "header_value": header_value
                }
            )

        # Show configuration form
        schema = vol.Schema({
            vol.Required("url_suffix", default="chirpstack"): str,
            vol.Optional("header_name", description="Optional authentication header name"): str,
            vol.Optional("header_value", description="Optional authentication header value"): str,
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class ChirpstackHttpOptionsFlow(config_entries.OptionsFlow):
    """ChirpStack REST API settings, needed to send downlinks (e.g. Vicki setpoints)."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        schema = vol.Schema({
            vol.Optional("api_url", description={"suggested_value": self.config_entry.options.get("api_url")}): str,
            vol.Optional("api_token", description={"suggested_value": self.config_entry.options.get("api_token")}): str,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
