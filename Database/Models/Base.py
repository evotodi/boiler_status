from __future__ import annotations

__all__ = [
    "BaseModel",
]

from peewee import *

class BaseModel(Model):
    pass
    # class Meta:
    #     database = Dbase.db
