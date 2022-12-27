from __future__ import annotations
import logging
import atexit
import signal
import sys

from Models.BoilerData import BoilerData
from Models.config import Config
from homie_spec import Node as HomieNode, Property as HomieProperty, Message as HomieMessage
from homie_spec.properties import Datatype as HomieDataType
from Utils.HomieDevice import Device as HomieDevice, DeviceState as HomieDeviceState
from Utils.MQTT import MQTT
from Utils.Boiler import Boiler

loglevel = logging.INFO
version: str = "1.0.4"
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
mqtt = MQTT()
config = Config()
boiler = Boiler()
currentBoilerData = BoilerData()
boilerDev = None  # type: HomieDevice or None

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
    logger.warning("Shutdown")
    _bds = boilerDev.getter_state(HomieDeviceState.DISCONNECTED.payload)
    mqtt.publishHomie(topic=_bds.topic, payload=_bds.payload, retain=_bds.retained, qos=_bds.qos)
    mqtt.stop()

def _publishHomie(device: HomieDevice, path: str):
    msg = device.getter_message(path).attrs
    # print(f"Message:: qos: {msg['qos']}   topic: {msg['topic']}  payload: {msg['payload']}")
    mqtt.publishHomie(topic=msg['topic'], payload=msg['payload'], retain=msg['retained'], qos=msg['qos'])

def publishBoilerDevice() -> HomieDevice:
    node = HomieNode(
        name="Boiler",
        typeOf="boiler",
        properties={
            "time": HomieProperty(name="Time", datatype=HomieDataType.STRING, get=lambda: currentBoilerData.ts.isoformat()),
            "cold_start": HomieProperty(name="Cold Start", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.coldStart else "OFF"),
            "high_limit": HomieProperty(name="High Limit", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.highLimit else "OFF"),
            "low_water": HomieProperty(name="Low Water", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.lowWater else "OFF"),
            "bypass": HomieProperty(name="Bypass", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.bypass else "OFF"),
            "fan": HomieProperty(name="Fan", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.fan else "OFF"),
            "shutdown": HomieProperty(name="Shutdown", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.shutdown else "OFF"),
            "alarm_light": HomieProperty(name="Alarm Light", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.alarmLt else "OFF"),
            "water_temp": HomieProperty(name="Water Temp", datatype=HomieDataType.FLOAT, unit="°F", get=lambda: f"{currentBoilerData.waterTemp:.2f}"),
            "o2": HomieProperty(name="Oxygen", datatype=HomieDataType.FLOAT, unit="%", get=lambda: f"{currentBoilerData.o2:.2f}"),
            "bot_air": HomieProperty(name="Bottom Air", datatype=HomieDataType.FLOAT, get=lambda: f"{currentBoilerData.botAir:.2f}"),
            "bot_air_pct": HomieProperty(name="Bottom Air Pct", datatype=HomieDataType.FLOAT, unit="%", get=lambda: f"{currentBoilerData.botAirPct:.2f}"),
            "top_air": HomieProperty(name="Top Air", datatype=HomieDataType.FLOAT, get=lambda: f"{currentBoilerData.topAir:.2f}"),
            "top_air_pct": HomieProperty(name="Top Air Pct", datatype=HomieDataType.FLOAT, unit="%", get=lambda: f"{currentBoilerData.topAirPct:.2f}"),
            "wood": HomieProperty(name="Wood", datatype=HomieDataType.BOOLEAN, get=lambda: "ON" if currentBoilerData.wood else "OFF"),
            "status": HomieProperty(name="Status", datatype=HomieDataType.STRING, get=lambda: currentBoilerData.status.title()),
        }
    )
    _boilerDevice = HomieDevice(id="boiler", name="Boiler", nodes={"heatmaster": node}, fw=version)
    for x in _boilerDevice.messages():  # type: HomieMessage
        mqtt.publishHomie(topic=x.topic, payload=x.payload, retain=x.retained, qos=x.qos)
    logger.info("Created MQTT Boiler Device")
    return _boilerDevice

def publishBoilerData(boilerDevice: HomieDevice):
    _publishHomie(boilerDevice, 'heatmaster/time')
    _publishHomie(boilerDevice, 'heatmaster/cold_start')
    _publishHomie(boilerDevice, 'heatmaster/high_limit')
    _publishHomie(boilerDevice, 'heatmaster/low_water')
    _publishHomie(boilerDevice, 'heatmaster/bypass')
    _publishHomie(boilerDevice, 'heatmaster/fan')
    _publishHomie(boilerDevice, 'heatmaster/shutdown')
    _publishHomie(boilerDevice, 'heatmaster/alarm_light')
    _publishHomie(boilerDevice, 'heatmaster/water_temp')
    _publishHomie(boilerDevice, 'heatmaster/o2')
    _publishHomie(boilerDevice, 'heatmaster/bot_air')
    _publishHomie(boilerDevice, 'heatmaster/bot_air_pct')
    _publishHomie(boilerDevice, 'heatmaster/top_air')
    _publishHomie(boilerDevice, 'heatmaster/top_air_pct')
    _publishHomie(boilerDevice, 'heatmaster/wood')
    _publishHomie(boilerDevice, 'heatmaster/status')
    logger.info("Published Boiler MQTT Data")

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)-16s %(levelname)-8s %(message)s', level=loglevel)
    # mqtt.verbose = True
    mqtt.begin()

    currentBoilerData = boiler.getData()
    boilerDev = publishBoilerDevice()

    while True:
        if boiler.timeToUpdate():
            logger.info("Time to update boiler")
            currentBoilerData = boiler.getData()
            publishBoilerData(boilerDev)
