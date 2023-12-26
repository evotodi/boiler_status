from __future__ import annotations

__all__ = [
    "BoilerData",
    "BoilerStatus",
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
    ERROR = "ERROR"  # Not actual status message.
    NONE = ""  # Not actual status message.

class BoilerData(BaseModel):
    ts: Optional[arrow.Arrow]
    coldStart: bool = None  # ON = cold start pressed
    highLimit: bool = None  # ON = temp to high
    lowWater: bool = None  # ON = water low
    bypass: bool = None  # ON = bypass lever open
    fan: bool = None  # ON = fan running
    shutdown: bool = None  # ON = boiler shutdown, OFF = boiler ok
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

    class Config:
        arbitrary_types_allowed = True
