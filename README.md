# ChirpStack HTTP Integration for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]

A Home Assistant integration that allows you to receive LoRaWAN device data from ChirpStack via HTTP integration.

## Features

  * Creates devices with binary_sensors and sensors.
  * Basic unit of measurement detection.
  * Supports configuring multiple platforms / endpoints.
  * Header authentication.
  * Entities and their last values survive Home Assistant restarts.
  * MClimate Vicki: a climate entity (set target temperature) and a child lock switch.
  * `chirpstack_http.send_downlink` action to send raw hex downlinks to any device.

## Requirements

  * Your home assistant http port to be accessible from chirpstack.
  * Chirpstack needs to decode the uplink with a codec. This component does not support decoding.

## Installation

### HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance.
2. Search for "ChirpStack HTTP Integration" in the HACS store.
3. Install the integration.
4. Restart Home Assistant.

### Manual Installation

1. Download the latest release from the [releases page][releases].
2. Create a `custom_components/chirpstack_http` directory in your Home Assistant configuration directory.
3. Extract the downloaded release into the newly created directory.
4. Restart Home Assistant.

## Configuration

1. Go to **Settings** > **Devices & Services** in your Home Assistant instance.
2. Click on **+ Add Integration** and search for "ChirpStack HTTP Integration".
3. Follow the configuration wizard to set up the integration.

## ChirpStack Configuration

1. In your ChirpStack application, go to **Integrations** > **HTTP**.
2. Add a new HTTP integration with the following URL:
    ```
    http://your-home-assistant-url:8123/api/chirpstack_http/<url_suffix>
    ```
3. OPTIONAL: Add http header and value if you configured it in home assistant.
4. Ensure your Home Assistant instance is accessible from your ChirpStack server.

## Downlinks (optional)

Controlling devices (Vicki setpoint, child lock, `send_downlink`) needs the ChirpStack REST API
([chirpstack-rest-api](https://github.com/chirpstack/chirpstack-rest-api)) reachable from Home Assistant.

1. In ChirpStack, create an API key under **API keys**.
2. In Home Assistant, open the integration and click **Configure**.
3. Enter the REST API URL (e.g. `http://<chirpstack-host>:8090`) and the API key.

LoRaWAN class A devices like the Vicki only receive downlinks right after they send an uplink, so changes
apply on the device's next check-in. The new setpoint is shown immediately and kept until the device confirms it.

## Usage

Once configured, the integration will create sensors for each data point received from your ChirpStack devices.

## Support

If you encounter any issues or have questions, please [open an issue][issues] on GitHub.

[commits-shield]: https://img.shields.io/github/commit-activity/y/AlexAsplund/chirpstack_http.svg
[commits]: https://github.com/AlexAsplund/chirpstack_http/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg
[issues]: https://github.com/AlexAsplund/chirpstack_http/issues
[license]: https://github.com/AlexAsplund/chirpstack_http/blob/main/LICENSE
[license-shield]: https://img.shields.io/github/license/AlexAsplund/chirpstack_http.svg
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40AlexASplund-blue.svg
[releases-shield]: https://img.shields.io/github/release/AlexAsplund/chirpstack_http.svg
[releases]: https://github.com/AlexAsplund/chirpstack_http/releases
[user_profile]: https://github.com/AlexAsplund