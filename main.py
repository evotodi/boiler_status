from __future__ import annotations
import logging
import atexit
import os
import signal
import sys
import requests
import arrow
from paho.mqtt.client import MQTTMessage

from Models.BoilerData import BoilerData, BoilerStatus
from Models.config import Config
from homie_spec import Node as HomieNode, Property as HomieProperty, Message as HomieMessage
from homie_spec.properties import Datatype as HomieDataType
from Utils.HomieDevice import Device as HomieDevice, DeviceState as HomieDeviceState
from Utils.MQTT import MQTT
from Utils.Boiler import Boiler
from Database.Database import Dbase

loglevel = os.environ.get("LOGLEVEL", "INFO").upper()
version: str = "1.0.7"
_registered_exit_funcs = set()
_executed_exit_funcs = set()
_exit_signals = frozenset([
        signal.SIGTERM,  # sent by kill cmd by default
        signal.SIGINT,  # CTRL ^ C, aka KeyboardInterrupt
        signal.SIGQUIT,  # CTRL ^ D
        # signal.SIGHUP,  # terminal closed or daemon rotating files
        signal.SIGABRT,  # os.abort()
    ])

logger = logging.getLogger()
# noinspection PyTypeChecker
db: Dbase = None
createDbTables: bool = False
# noinspection PyTypeChecker
mqtt: MQTT = None
# noinspection PyTypeChecker
node: HomieNode = None
boilerDev: HomieDevice = HomieDevice(id="boiler", name="Boiler", fw=version, nodes={'heatmaster': node})
config = Config()
# noinspection PyTypeChecker
boiler: Boiler = None
currentBoilerData = BoilerData()
lastPublishHomie: arrow.Arrow = arrow.utcnow()

topicWoodFilled = f"{boilerDev.prefix}/{boilerDev.id}/heatmaster/wood_filled/set"

def register_exit_func(fun, signals=_exit_signals):
    """Register a function which will be executed on clean interpreter
    exit or in case one of the `signals` is received by this process
    (differently from atexit.register()).
    Also, it makes sure to execute any previously registered signal
    handler as well. If any, it will be executed after `fun`.
    Functions which were already registered or executed will be
    skipped.
    Exit function will not be executed on SIGKILL, SIGSTOP or
    os._exit(0).
    """
    def fun_wrapper():
        if fun not in _executed_exit_funcs:
            try:
                fun()
            finally:
                _executed_exit_funcs.add(fun)

    # noinspection PyUnusedLocal
    def signal_wrapper(signum=None, frame=None):
        if signum is not None:
            pass
            # You may want to add some logging here.
            # XXX: if logging module is used it may complain with
            # "No handlers could be found for logger"
            # smap = dict([(getattr(signal, x), x) for x in dir(signal)
            #              if x.startswith('SIG')])
            # print("signal {} received by process with PID {}".format(
            #     smap.get(signum, signum), os.getpid()))
        fun_wrapper()
        # Only return the original signal this process was hit with
        # in case fun returns with no errors, otherwise process will
        # return with sig 1.
        if signum is not None:
            sys.exit(signum)

    if not callable(fun):
        raise TypeError("{!r} is not callable".format(fun))
    # noinspection PySetFunctionToLiteral
    set([fun])  # raise exc if obj is not hash-able

    for sig in signals:
        # Register function for this signal and pop() the previously
        # registered one (if any). This can either be a callable,
        # SIG_IGN (ignore signal) or SIG_DFL (perform default action
        # for signal).
        old_handler = signal.signal(sig, signal_wrapper)
        if old_handler not in (signal.SIG_DFL, signal.SIG_IGN):
            # ...just for extra safety.
            if not callable(old_handler):
                continue
            # This is needed otherwise we'll get a KeyboardInterrupt
            # strace on interpreter exit, even if the process exited
            # with sig 0.
            if (sig == signal.SIGINT and
                    old_handler is signal.default_int_handler):
                continue
            # There was a function which was already registered for this
            # signal. Register it again so it will get executed (after our
            # new fun).
            if old_handler not in _registered_exit_funcs:
                atexit.register(old_handler)
                _registered_exit_funcs.add(old_handler)

    # This further registration will be executed in case of clean
    # interpreter exit (no signals received).
    if fun not in _registered_exit_funcs or not signals:
        atexit.register(fun_wrapper)
        _registered_exit_funcs.add(fun)

@register_exit_func
def shutdown():
    global currentBoilerData
    logger.warning("Shutdown")
    currentBoilerData = boiler.getPublisherShutdownData()
    makeHomieNode()
    publishBoilerData()
    publishBoilerStatus(HomieDeviceState.DISCONNECTED.payload)
    mqtt.stop()

def publishBoilerDevice():
    for x in boilerDev.messages():  # type: HomieMessage
        mqtt.publishHomie(topic=x.topic, payload=x.payload, retain=x.retained, qos=x.qos)
    logger.info("Created MQTT Boiler Device")

def publishBoilerData():
    for prop in boilerDev.nodes['heatmaster'].properties.keys():
        msg = boilerDev.getter_message(f"heatmaster/{prop}").attrs
        # print(f"Message:: qos: {msg['qos']}   topic: {msg['topic']}  payload: {msg['payload']}")
        mqtt.publishHomie(topic=msg['topic'], payload=msg['payload'], retain=msg['retained'], qos=msg['qos'])
    logger.info("Published Boiler MQTT Data")

def publishBoilerStatus(status: str):
    bds = boilerDev.getter_state(status)
    mqtt.publishHomie(topic=bds.topic, payload=bds.payload, retain=bds.retained, qos=bds.qos)

def makeHomieNode():
    global node, boilerDev

    node = HomieNode(
        name="Boiler",
        typeOf="boiler",
        properties={
            "time": HomieProperty(name="Time", datatype=HomieDataType.STRING, get=lambda: currentBoilerData.ts.isoformat()),
            "cold_start": HomieProperty(name="Cold Start", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.coldStart.value else "OFF"),
            "high_limit": HomieProperty(name="High Limit", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.highLimit else "OFF"),
            "low_water": HomieProperty(name="Low Water", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.lowWater else "OFF"),
            "bypass": HomieProperty(name="Bypass", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.bypass.value else "OFF"),
            "fan": HomieProperty(name="Fan", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.fan else "OFF"),
            "shutdown": HomieProperty(name="Shutdown", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.shutdown.value else "OFF"),
            "alarm_light": HomieProperty(name="Alarm Light", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.alarmLt else "OFF"),
            "water_temp": HomieProperty(name="Water Temp", datatype=HomieDataType.FLOAT, unit="°F", get=lambda: f"{currentBoilerData.waterTemp:.2f}"),
            "o2": HomieProperty(name="Oxygen", datatype=HomieDataType.FLOAT, unit="%", get=lambda: f"{currentBoilerData.o2:.2f}"),
            "bot_air": HomieProperty(name="Bottom Air", datatype=HomieDataType.FLOAT, get=lambda: f"{currentBoilerData.botAir:.2f}"),
            "bot_air_pct": HomieProperty(name="Bottom Air Pct", datatype=HomieDataType.FLOAT, unit="%", get=lambda: f"{currentBoilerData.botAirPct:.2f}"),
            "top_air": HomieProperty(name="Top Air", datatype=HomieDataType.FLOAT, get=lambda: f"{currentBoilerData.topAir:.2f}"),
            "top_air_pct": HomieProperty(name="Top Air Pct", datatype=HomieDataType.FLOAT, unit="%", get=lambda: f"{currentBoilerData.topAirPct:.2f}"),
            "wood_empty": HomieProperty(name="Wood Empty", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.woodEmpty else "OFF"),
            "wood_low": HomieProperty(name="Wood Low", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.woodLow else "OFF"),
            "condensing": HomieProperty(name="Condensing", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.condensing else "OFF"),
            "status": HomieProperty(name="Status", datatype=HomieDataType.STRING, get=lambda: currentBoilerData.status.value.title()),
            "last_bp_open": HomieProperty(name="Last Bypass Opened", datatype=HomieDataType.STRING, get=lambda: currentBoilerData.lastBypassOpened.isoformat()),
            "last_bp_open_human": HomieProperty(name="Last Bypass Opened Human", datatype=HomieDataType.STRING, get=lambda: currentBoilerData.lastBypassOpenedHuman.title()),
            "last_wood_fill": HomieProperty(name="Last Wood Fill", datatype=HomieDataType.STRING, get=lambda: currentBoilerData.lastWoodFilled.isoformat()),
            "last_wood_fill_human": HomieProperty(name="Last Wood Fill Human", datatype=HomieDataType.STRING, get=lambda: currentBoilerData.lastWoodFilledHuman.title()),

            "wood_filled": HomieProperty(name="Wood Filled", datatype=HomieDataType.STRING, get=lambda: "", set=lambda x: print(f"SET HERE = {x}"), settable=True)
        }
    )

    # noinspection PyUnresolvedReferences
    boilerDev.nodes['heatmaster'] = node

# noinspection PyUnusedLocal
def onMessage(client, userdata, message: MQTTMessage) -> None:
    logger.debug(f"userdata: {userdata}")
    logger.debug(f"message: Topic: {message.topic}  Payload: {message.payload}")

    if message.topic == topicWoodFilled and message.payload != "":
        logger.info(f"Wood Filled: {message.payload}")
        db.eventWoodFilled(ts=arrow.get(message.payload.decode()))
        boiler.woodFilled()

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)-16s %(levelname)-8s %(message)s', level=loglevel)

    logger.info(config.model_dump_json(indent=4))

    if not os.path.exists('./Store/db.sqlite'):
        createDbTables = True
    db = Dbase('./Store/db.sqlite')
    db.connect()
    if createDbTables:
        db.create_tables()

    boiler = Boiler(db=db)

    mqtt = MQTT(clientId=os.environ.get('MQTT_CLIENT_ID', default='boiler'), onMessage=onMessage)
    mqttDebug = False
    if 'MQTT_DEBUG' in os.environ:
        mqttDebug = True
    mqtt.debug = mqttDebug
    mqtt.subscribe(topic=topicWoodFilled, qos=1)
    mqtt.begin()

    try:
        currentBoilerData = boiler.getData()
    except requests.exceptions.ConnectionError as ce:
        print(ce)
        logger.warning("Boiler is offline")
        currentBoilerData = boiler.getOfflineData()

    makeHomieNode()
    publishBoilerDevice()

    if mqtt.disconnectCode == 7:
        raise OSError("MQTT Client ID exists! Another boiler program is running")

    publishBoilerData()

    while True:
        """ Boiler Publish """
        if boiler.timeToUpdate():
            logger.info("Time to update boiler")

            try:
                currentBoilerData = boiler.getData()
            except requests.exceptions.ConnectionError as ce:
                print(ce)
                logger.warning("Boiler is offline")
                currentBoilerData = boiler.getOfflineData()

            publishBoilerData()

        """ Homie Status Publish """
        if arrow.utcnow().shift(seconds=-config.homiePublishStatusSeconds) > lastPublishHomie:
            if currentBoilerData.status == BoilerStatus.OFFLINE:
                publishBoilerStatus(HomieDeviceState.LOST.payload)
            else:
                publishBoilerStatus(HomieDeviceState.READY.payload)

            lastPublishHomie = arrow.utcnow()
