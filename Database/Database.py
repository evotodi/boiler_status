import json
import sqlite3
from datetime import datetime

import arrow
from peewee import SqliteDatabase
from .Models.Event import Event, EventType, EventData

class Dbase:
    db = SqliteDatabase(None)
    connection: sqlite3.Connection = None

    def __init__(self, database_name):
        self.db.init(database_name)

    def connect(self):
        self.db.connect()
        self.connection = self.db.connection()
        self.db.bind([Event])

    def create_tables(self):
        self.db.create_tables([Event])

    @classmethod
    def _addEvent(cls, event: EventType, value: str = None, ts: arrow.Arrow = None):
        if ts is None:
            ts = datetime.now()
        else:
            ts = ts.naive

        Event.create(ts=ts, eventType=event.value, value=value)

    @classmethod
    def eventWoodFilled(cls, ts: arrow.Arrow = None):
        cls._addEvent(event=EventType.WoodFilled, ts=ts, value=json.dumps(True))

    @classmethod
    def eventShutdown(cls, value: bool, ts: arrow.Arrow = None):
        cls._addEvent(event=EventType.Shutdown, ts=ts, value=json.dumps(value))

    @classmethod
    def eventBypassOpened(cls, value: bool, ts: arrow.Arrow = None):
        cls._addEvent(event=EventType.Bypass, ts=ts, value=json.dumps(value))

    @classmethod
    def eventColdStart(cls, value: bool, ts: arrow.Arrow = None):
        cls._addEvent(event=EventType.ColdStart, ts=ts, value=json.dumps(value))

    @classmethod
    def eventHeating(cls, value: bool, ts: arrow.Arrow):
        cls._addEvent(event=EventType.Heating, ts=ts, value=json.dumps(value))

    @classmethod
    def lastBypassOpened(cls) -> EventData:
        x = Event.select().where(Event.eventType == EventType.Bypass.value).order_by(Event.ts.desc()).limit(1).first()  # type: Event
        try:
            ts = arrow.get(x.ts)
        except AttributeError:
            ts = arrow.get(0)

        if x is not None:
            return EventData(eventType=EventType(x.eventType), ts=ts, value=json.loads(x.value))
        else:
            return EventData(eventType=EventType.Bypass, ts=ts, value=True)

    @classmethod
    def lastHeating(cls) -> EventData or None:
        x = Event.select().where(Event.eventType == EventType.Heating.value).order_by(Event.ts.desc()).limit(1).first()  # type: Event
        if x is not None:
            return EventData(eventType=EventType(x.eventType), ts=arrow.get(x.ts), value=json.loads(x.value))

        return None

    @classmethod
    def lastWoodFilled(cls) -> EventData:
        x = Event.select().where(Event.eventType == EventType.WoodFilled.value).order_by(Event.ts.desc()).limit(1).first()  # type: Event
        try:
            ts = arrow.get(x.ts)
        except AttributeError:
            ts = arrow.get(0)

        if x is not None:
            return EventData(eventType=EventType(x.eventType), ts=ts, value=json.loads(x.value))
        else:
            return EventData(eventType=EventType.WoodFilled, ts=ts, value=True)
