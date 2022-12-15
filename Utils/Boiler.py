from __future__ import annotations

__all__ = [
    "Boiler",
]

import logging
import zlib
from random import randint
from typing import Any

import arrow
import requests
import xml.etree.ElementTree as ET

from Models.BoilerData import BoilerData
from Models.config import Config

class Boiler:
    logger = logging.getLogger()
    lastUpdate = arrow.get(0)
    boilerData = BoilerData()
    _token = None
    _secA1 = None
    _secA2 = None
    _secB1 = None
    _secB2 = None
    CLOSED = "ON"
    OPEN = "OFF"

    def __init__(self):
        self.config = Config()

    @staticmethod
    def _regressO2(val: int) -> float:
        terms = [
            -3.2800164689422040e-002,
            2.5190236792343140e-002
        ]

        t = 1
        r = 0
        for c in terms:
            r += c * t
            t *= val
        return r

    @staticmethod
    def _regressTemp(val: int) -> float:
        terms = [
            -3.9591205241676192e+001,
            2.5131750271267950e-001
        ]

        t = 1
        r = 0
        for c in terms:
            r += c * t
            t *= val
        return r

    def _login(self) -> bool:
        if self._secA1 is None:
            self._secA1 = randint(0, 4294967296)
        if self._secA2 is None:
            self._secA2 = randint(0, 4294967296)
        if self._secB1 is None:
            self._secB1 = randint(0, 4294967296)
        if self._secB2 is None:
            self._secB2 = randint(0, 4294967296)

        req1 = requests.post(url=self.config.hmUrl, headers={'Security-Hint': 'p'}, data=f"UAMCHAL:3,4,{self._secA1},{self._secA2},{self._secB1},{self._secB2}")
        # print(f"Login response = {req.text}")
        ret = req1.text.split(',')
        if len(ret) == 3 and ret[0] == "700":
            pwToken = f"{self.config.passwd}+{ret[2]}"
            pwToken = pwToken[0:32]
            # print(f"pwToken = {pwToken}")
            pwTokenCrc = zlib.crc32(pwToken.encode())
            iPWToken = pwTokenCrc ^ int(ret[2])
            # print(f"iPWToken = {iPWToken}")
            iServerChallenge = (((self._secA1 ^ self._secA2) ^ self._secB1) ^ self._secB2) ^ int(ret[2])
            # print(f"iServerChallenge = {iServerChallenge}")
            req2 = requests.post(url=self.config.hmUrl, headers={'Security-Hint': f'{ret[1]}'}, data=f"UAMLOGIN:Web User,{iPWToken},{iServerChallenge}")
            # print(f"Login response = {req.text}")
            data = req2.text.split(',')
            if len(data) == 2 and data[0] == '700':
                self._token = data[1]
                return True
            else:
                print("Login failed")
                self.logger.error(f"Login failed: {req1.text}")
                return False

    def _parseXml(self, xml: str) -> int or None:
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            self.logger.error(f"Failed to parse: {xml}")
            return None
        val = root.find('r').get('v', default=None)
        if val is None:
            return val
        return int(val, 16)

    def _updateBoiler(self):
        bd = BoilerData()
        if self._token is None:
            for _ in range(0, 4):
                if self._login():
                    break
            else:
                self.boilerData = None
                return

        bd.ts = arrow.utcnow()

        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETSTDG")
        if "Running" not in req.text:
            self.logger.info("Logging in after timeout")
            for _ in range(0, 4):
                if self._login():
                    break
            else:
                self.boilerData = None
                return

        # Fan
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,130,0,0,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.fan = self.CLOSED
            else:
                bd.fan = self.OPEN

        # Shutdown
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,130,0,1,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.shutdown = self.OPEN
            else:
                bd.shutdown = self.CLOSED

        # Alarm Lt
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,130,0,2,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.alarmLt = self.CLOSED
            else:
                bd.alarmLt = self.OPEN

        # Low Water
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,129,0,0,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.lowWater = self.OPEN
            else:
                bd.lowWater = self.CLOSED

        # Bypass
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,129,0,1,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.bypass = self.OPEN
            else:
                bd.bypass = self.CLOSED

        # Cold Start
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,129,0,2,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.coldStart = self.CLOSED
            else:
                bd.coldStart = self.OPEN

        # High Limit
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,129,0,3,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.highLimit = self.OPEN
            else:
                bd.highLimit = self.CLOSED

        # Bot Air
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,19,0,0,4,1")
        val = self._parseXml(req.text)
        if val is not None:
            val1 = float(int(f"{val:0{4}x}", 16)) * 0.1
            bd.botAir = val1

        # Top Air
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,19,0,1,4,1")
        val = self._parseXml(req.text)
        if val is not None:
            val1 = float(int(f"{val:0{4}x}", 16)) * 0.1
            bd.topAir = val1

        # Water Temp / O2
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,18,0,0,4,2")
        val = self._parseXml(req.text)
        if val is not None:
            val1 = int(f"{val:0{8}x}"[0:4], 16)
            val2 = int(f"{val:0{8}x}"[4:8], 16)

            bd.waterTemp = self._regressTemp(val1)
            bd.o2 = self._regressO2(val2)

        self.lastUpdate = arrow.utcnow()
        self.logger.info(f"Boiler updated. < {self.lastUpdate} >")
        self.boilerData = bd

    def getData(self) -> BoilerData:
        if arrow.utcnow().shift(seconds=-self.config.updateBoilerSeconds) > self.lastUpdate:
            self._updateBoiler()
        self.logger.info(f"Boiler last updated at {self.lastUpdate}")

        return self.boilerData

    def timeToUpdate(self) -> bool:
        if arrow.utcnow().shift(seconds=-self.config.updateBoilerSeconds) > self.lastUpdate:
            return True

        return False
