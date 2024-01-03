import json
from datetime import datetime
from enum import Enum

import arrow
from peewee import *

class Events(Enum):
    WoodFilled = "wood_filled"
    Shutdown = "shutdown"
    Bypass = "bypass"
    ColdStart = "cold_start"

class Dbase:
    db = SqliteDatabase(None)

    def __init__(self, database_name):
        self.db.init(database_name)

    def connect(self):
        self.db.connect()

    def create_tables(self):
        self.db.create_tables([Event])

    @classmethod
    def _addEvent(cls, event: Events, value: str = None, ts: arrow.Arrow = None):
        if ts is None:
            ts = datetime.now()
        else:
            ts = ts.datetime

        Event.create(ts=ts, eventType=event.value, value=value)

    @classmethod
    def eventWoodFilled(cls, ts: arrow.Arrow = None):
        cls._addEvent(event=Events.WoodFilled, ts=ts, value=json.dumps(True))

    @classmethod
    def eventShutdown(cls, value: bool, ts: arrow.Arrow = None):
        cls._addEvent(event=Events.Shutdown, ts=ts, value=json.dumps(value))

    @classmethod
    def eventBypassOpened(cls, value: bool, ts: arrow.Arrow = None):
        cls._addEvent(event=Events.Bypass, ts=ts, value=json.dumps(value))

    @classmethod
    def eventColdStart(cls, value: bool, ts: arrow.Arrow = None):
        cls._addEvent(event=Events.ColdStart, ts=ts, value=json.dumps(value))

    @classmethod
    def lastBypassOpened(cls) -> arrow.Arrow:
        # noinspection PyUnresolvedReferences
        x = Event.select().where(Event.eventType == Events.Bypass.value).order_by(Event.ts.desc()).limit(1).first()  # type: Event
        try:
            # noinspection PyTypeChecker
            return arrow.get(x.ts)
        except AttributeError:
            return arrow.get(0)


class BaseModel(Model):
    class Meta:
        database = Dbase.db

class Event(BaseModel):
    eventType = CharField(max_length=50)
    ts = DateTimeField(default=datetime.now)
    value = CharField(max_length=50)
