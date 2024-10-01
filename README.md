# Heatmaster Boiler MQTT Publisher
This python script publishes a Homie

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

In Models/config.py reference the field aliases for allowed environment variables 


