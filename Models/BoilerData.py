from __future__ import annotations

__all__ = [
    "BoilerData",
    "BoilerStatus",
    "TrackedBool"
]

from typing import Optional

import arrow
from pydantic import BaseModel
from enum import Enum

class BoilerStatus(Enum):
    TIMER_CYCLE = "timer cycle"
    IDLE = "idle"
    HEATING = "heating cycle"
    COLD_START = "cold start mode"
    LOW_TEMP = "low temp"
    OFFLINE = "offline"
    ALARM = "alarm"
    ERROR = "ERROR"  # Not actual status message.
    PUB_SHUTDOWN = "PUBLISHER SHUTDOWN"  # Not actual status message.
    NONE = ""  # Not actual status message.

class TrackedBool:
    changed: bool = False
    _value: bool = False

    def __init__(self, default: bool):
        self._value: bool = default

    def __bool__(self) -> bool:
        return self._value

    @property
    def value(self) -> bool:
        return self._value

    @value.setter
    def value(self, val: bool):
        if self._value != val:
            self._value = val
            self.changed = True
        else:
            self.changed = False

class BoilerData(BaseModel):
    ts: Optional[arrow.Arrow] = None
    coldStart: TrackedBool = TrackedBool(False)  # ON = cold start pressed
    highLimit: bool = None  # ON = temp to high
    lowWater: bool = None  # ON = water low
    bypass: TrackedBool = TrackedBool(False)  # ON = bypass lever open
    fan: bool = None  # ON = fan running
    shutdown: TrackedBool = TrackedBool(False)  # ON = boiler shutdown, OFF = boiler ok
    alarmLt: bool = None  # ON = alarm light on
    waterTemp: float = 0.0
    o2: float = 0.0
    botAir: float = 0.0
    topAir: float = 0.0
    botAirPct: float = 0.0
    topAirPct: float = 0.0
    woodEmpty: bool = False  # OFF = Wood gone, ON = Plenty of wood
    woodLow: bool = False  # OFF = Heating properly, ON = Boiler still hot but cooling off
    status: BoilerStatus = BoilerStatus.NONE  # Boiler status
    waterSlope: float = 0.0
    o2Slope: float = 0.0
    o2Avg: float = 0.0
    tempAvg: float = 0.0
    heatingStart: Optional[arrow.Arrow] = None  # When the heating cycle started
    condensing: bool = False  # ON = Creosote forming, OFF = Heating properly
    lastBypassOpened: Optional[arrow.Arrow] = arrow.get(0)
    lastBypassOpenedHuman: str = ""
    lastWoodFilled: Optional[arrow.Arrow] = arrow.get(0)
    lastWoodFilledHuman: str = ""

    class Config:
        arbitrary_types_allowed = True
