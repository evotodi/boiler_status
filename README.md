# Heatmaster Boiler MQTT Publisher
This python script publishes a Homie v4 device for Heatmaster boilers using the Siemens controller.
I use this to monitor my boiler status in my home automation to provide alerts when the boiler needs fed.
See the list of [MQTT properties](#mqtt-properties) below for what is published.  

My docker-compose file is provided for an example

### Environment Variables

#### Required
| Name           | Type   | Description                                          |
|----------------|--------|------------------------------------------------------|
| MQTT_BROKER    | String | MQTT broker URL                                      |
| MQTT_USER      | String | MQTT Username                                        |
| MQTT_PASSWORD  | String | MQTT Password                                        |
| HM_URL         | String | Heatmaster url in the form of http(s)://ip_or_domain |

#### Optional
| Name           | Type   | Default | Description                                       |
|----------------|--------|---------|---------------------------------------------------|
| LOG_LEVEL      | String | INFO    | Python loglevel. INFO, DEBUG, ERROR, WARNING      |
| MQTT_CLIENT_ID | String | boiler  | Sets the client id for the MQTT client connection |
| MQTT_DEBUG     | ANY    | False   | When present enables MQTT debugging               |

#### In Models/config.py reference the field aliases for allowed environment variables 

### MQTT Properties
| Property             | Type     |
|----------------------|----------|
| time                 | datetime |
| cold_start           | bool     |
| high_limit           | bool     |
| low_water            | bool     |
| bypass               | bool     |
| fan                  | bool     |
| shutdown             | bool     |
| alarm_light          | bool     |
| water_temp           | float    |
| o2                   | float    |
| bot_air              | float    |
| bot_air_pct          | float    |
| top_air              | float    |
| top_air_pct          | float    |
| wood_empty           | bool     |
| wood_low             | bool     |
| condensing           | bool     |
| status               | string   |
| last_bp_open         | datetime |
| last_bp_open_human   | datetime |
| last_wood_fill       | datetime |
| last_wood_fill_human | datetime |
| wood_filled          | string   |

