from __future__ import annotations

__all__ = [
    "Event",
    "EventType",
    "EventData",
]

import dataclasses
from datetime import datetime
from enum import Enum

import arrow
from peewee import *
from .Base import BaseModel

class EventType(Enum):
    WoodFilled = "wood_filled"
    Shutdown = "shutdown"
    Bypass = "bypass"
    ColdStart = "cold_start"
    Heating = "heating"

@dataclasses.dataclass
class EventData:
    eventType: EventType
    ts: arrow.Arrow
    value: bool

class Event(BaseModel):
    eventType = CharField(max_length=50)
    ts = DateTimeField(default=datetime.now)
    value = CharField(max_length=50)
