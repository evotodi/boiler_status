from __future__ import annotations

__all__ = [
    "BoilerData",
]

from typing import Optional

import arrow
from pydantic import BaseModel

class BoilerData(BaseModel):
    ts: Optional[arrow.Arrow]
    coldStart: str = None
    highLimit: str = None
    lowWater: str = None
    bypass: str = None
    fan: str = None
    shutdown: str = None
    alarmLt: str = None
    waterTemp: float = 0.0
    o2: float = 0.0
    botAir: float = 0.0
    topAir: float = 0.0

    class Config:
        arbitrary_types_allowed = True
