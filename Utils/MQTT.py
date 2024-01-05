from __future__ import annotations

__all__ = [
    "MQTT",
]

from typing import TYPE_CHECKING, Callable, List, Tuple
import time
import logging

import paho.mqtt.client
import paho.mqtt.client as mqtt
from Models.config import Config

if TYPE_CHECKING:
    import logging

class MQTT:
    logger = logging.getLogger()
    _began = False
    _subscriptions: List[Tuple[str, int]] = []
    _onMessage: Callable = None
    _onConnect: Callable = None
    _onDisconnect: Callable = None
    _onSubscribe: Callable = None
    _debug = False
    _mqttVerbose: bool = False
    disconnectCode: int = 0

    def __init__(self, clientId: str, onMessage: Callable, onConnect: Callable = None, onDisconnect: Callable = None, onSubscribe: Callable = None):
        self.client = mqtt.Client(protocol=paho.mqtt.client.MQTTv311, client_id=clientId, clean_session=False)
        self.config = Config()
        self._onMessage = onMessage
        self._onConnect = onConnect
        self._onDisconnect = onDisconnect
        self._onSubscribe = onSubscribe

    def begin(self):
        if self._mqttVerbose:
            self.client.enable_logger(self.logger)

        self.client.on_message = self._onMessage

        if self._onConnect is not None:
            self.client.on_connect = self._onConnect
        else:
            self.client.on_connect = self._onConnectDefault

        if self._onDisconnect is not None:
            self.client.on_disconnect = self._onDisconnect
        else:
            self.client.on_disconnect = self._onDisconnectDefault

        if self._onSubscribe is not None:
            self.client.on_subscribe = self._onSubscribe
        else:
            self.client.on_subscribe = self._onSubscribeDefault

        self.client.max_inflight_messages_set(100)
        self.client.username_pw_set(username=self.config.mqttUser, password=self.config.mqttPasswd)
        self.client.connect(self.config.mqttServer)
        self._began = True
        self.client.loop_start()

    def publishHomie(self, topic, payload, retain=False, qos=0):
        self.client.publish(topic=topic, payload=payload, retain=retain, qos=qos)
        time.sleep(0.02)

    def stop(self):
        self.client.loop_stop(True)
        self.client.disconnect()
        self._began = False

    def restart(self):
        self.logger.warning("Restart of MQTT requested")
        self.stop()
        time.sleep(3)
        self.begin()

    def subscribe(self, topic, qos=0):
        if self._began:
            raise Exception("MQTT already began")

        self._subscriptions.append((topic, qos))
        if self._debug:
            self.logger.debug(f"Subscribed to {topic} with qos: {qos}")

    # noinspection PyUnusedLocal
    def _onConnectDefault(self, client, userdata, flags, rc):
        if self._debug:
            self.logger.debug(f"Connected with result code {rc}")
        if len(self._subscriptions) > 0:
            client.subscribe(self._subscriptions)

    # noinspection PyUnusedLocal
    def _onDisconnectDefault(self, client, userdata, rc):
        self.disconnectCode = rc
        if self._debug:
            self.logger.debug(f"Disconnected with result code {rc}")

    # noinspection PyUnusedLocal
    def _onSubscribeDefault(self, client, userdata, mid, granted_qos):
        if self._debug:
            self.logger.debug(f"Subscribed with mid {mid} and qos {granted_qos}")

    @property
    def mqttVerbose(self):
        return self._mqttVerbose

    @mqttVerbose.setter
    def mqttVerbose(self, enabled):
        self._mqttVerbose = enabled

    @property
    def debug(self):
        return self._debug

    @debug.setter
    def debug(self, enabled):
        self._debug = enabled
