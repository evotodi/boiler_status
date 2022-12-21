from __future__ import annotations

__all__ = [
    "BoilerData",
]

from typing import Optional

import arrow
from pydantic import BaseModel

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
    wood: bool = None  # ON = has wood, OFF = wood gone

    class Config:
        arbitrary_types_allowed = True
