```
[![](https://img.shields.io/github/v/release/Verbalinsurection/next_rocket_launch.svg?include_prereleases)](https://github.com/Verbalinsurection/next_rocket_launch/releases)
![GitHub Release Date](https://img.shields.io/github/release-date/Verbalinsurection/next_rocket_launch)
[![GitHub](https://img.shields.io/github/license/Verbalinsurection/next_rocket_launch)](LICENSE)
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
```

# Next Rocket Launch

The `Next Rocket Launch` sensor platform allows you to monitor the next rocket launch from Teamup.
Unlike launch_library, this integration allows you to obtain the next launch information for the rocket name interest you.

## Installation

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `next_rocket_launch`.
4. Download _all_ the files from the `custom_components/next_rocket_launch/` directory (folder) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Restart Home Assistant.
7. Move on to the configuration.

Using your HA configuration directory (folder) as a starting point you should now also have this:

```text
custom_components/next_rocket_launch/__init__.py
custom_components/next_rocket_launch/manifest.json
custom_components/next_rocket_launch/sensor.py
```

## Example configuration.yaml

```yaml
sensor:
  - platform: next_rocket_launch
    rocket_name:
      - "Ariane"
      - "Falcon"
```

### Configuration options

Key | Type | Required | Description
-- | -- | -- | --
`rocket_name` | `list` | `False` | Name of the rocket to track.(default is `ALL`)
