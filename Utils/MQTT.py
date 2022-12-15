from __future__ import annotations

__all__ = [
    "MQTT",
]

from typing import TYPE_CHECKING
import json
import time
import logging

import arrow
import paho.mqtt.client
import paho.mqtt.client as mqtt
from Models.config import Config

if TYPE_CHECKING:
    import logging

class MQTT:
    logger = logging.getLogger()

    def __init__(self, debug=False):
        self._debug = debug
        self._quiet = False
        self.client = mqtt.Client(protocol=paho.mqtt.client.MQTTv311, client_id='weatherPublisher', clean_session=False)
        self.config = Config()

    def begin(self):
        if self._debug:
            self.client.enable_logger(self.logger)

        self.client.max_inflight_messages_set(100)
        self.client.username_pw_set(username=self.config.mqttUser, password=self.config.mqttPasswd)
        self.client.connect(self.config.mqttServer)
        self.client.loop_start()

    def publishHomie(self, topic, payload, retain=False, qos=0):
        self.client.publish(topic=topic, payload=payload, retain=retain, qos=qos)
        time.sleep(0.02)

    def stop(self):
        self.client.loop_stop(True)
        self.client.disconnect()

    def restart(self):
        self.logger.warning("Restart of MQTT requested")
        self.stop()
        time.sleep(3)
        self.begin()

    @property
    def verbose(self):
        return self._debug

    @verbose.setter
    def verbose(self, enabled):
        self._debug = enabled

    @property
    def quiet(self):
        return self._quiet

    @quiet.setter
    def quiet(self, enabled):
        self._quiet = enabled
