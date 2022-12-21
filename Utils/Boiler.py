from __future__ import annotations

__all__ = [
    "Boiler",
]

import logging
import zlib
from random import randint
import numpy as np
from scipy.stats import linregress
from typing import TYPE_CHECKING

import arrow
import requests
import xml.etree.ElementTree as ET

from Models.BoilerData import BoilerData
from Models.config import Config

if TYPE_CHECKING:
    from scipy.stats._stats_mstats_common import LinregressResult

class Boiler:
    logger = logging.getLogger()
    lastUpdate = arrow.get(0)
    boilerData = BoilerData()
    _token = None
    _secA1 = None
    _secA2 = None
    _secB1 = None
    _secB2 = None
    _slopeArrayLen = 8
    _lastXs = np.arange(stop=_slopeArrayLen)
    _lastO2s = np.full(shape=(_slopeArrayLen,), fill_value=6.0, dtype=np.float64)
    _lastTemps = np.full(shape=(_slopeArrayLen,), fill_value=180.0, dtype=np.float64)
    _firstFun = True

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

    @staticmethod
    def _translate(value: float, leftMin: float, leftMax: float, rightMin: float, rightMax: float) -> float:
        # Figure out how 'wide' each range is
        leftSpan = leftMax - leftMin
        rightSpan = rightMax - rightMin

        # Convert the left range into a 0-1 range (float)
        valueScaled = float(value - leftMin) / float(leftSpan)

        # Convert the 0-1 range into a value in the right range.
        return rightMin + (valueScaled * rightSpan)

    @staticmethod
    def _translate2(value: float, inMin: float, inMax: float, outMin: float, outMax: float):
        return outMin + (float(value - inMin) / float(inMax - inMin) * (outMax - outMin))

    @staticmethod
    def _rangePercent(val: float, valMin: float, valMax: float) -> float:
        x = ((val - valMin) * 100) / (valMax - valMin)
        if x < 0.0:
            x = 0.0
        if x > 100.0:
            x = 100.0
        return x

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

    def _addWaterTemp(self, val: float):
        self._lastTemps = np.append(self._lastTemps, val)
        self._lastTemps = np.delete(self._lastTemps, 0)
        self.logger.debug(f"LastWaterTemps: {self._lastTemps}")

    def _addO2(self, val: float):
        self._lastO2s = np.append(self._lastO2s, val)
        self._lastO2s = np.delete(self._lastO2s, 0)
        self.logger.debug(f"LastO2s: {self._lastO2s}")

    def _slopeWater(self) -> float:
        lr = linregress(self._lastXs, self._lastTemps)  # type: LinregressResult
        self.logger.debug(f"Water linear regression: {lr}")
        return lr.slope

    def _avgO2(self) -> float:
        return np.average(self._lastO2s)

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
                bd.fan = True
            else:
                bd.fan = False

        # Shutdown
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,130,0,1,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.shutdown = False
            else:
                bd.shutdown = True

        # Alarm Lt
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,130,0,2,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.alarmLt = True
            else:
                bd.alarmLt = False

        # Low Water
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,129,0,0,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.lowWater = False
            else:
                bd.lowWater = True

        # Bypass
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,129,0,1,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.bypass = False
            else:
                bd.bypass = True

        # Cold Start
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,129,0,2,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.coldStart = True
            else:
                bd.coldStart = False

        # High Limit
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,129,0,3,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.highLimit = False
            else:
                bd.highLimit = True

        # Bot / Top Air
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,19,0,0,4,2")
        val = self._parseXml(req.text)
        if val is not None:
            val1 = float(int(f"{val:0{8}x}"[0:4], 16)) * 0.1
            val2 = float(int(f"{val:0{8}x}"[4:8], 16)) * 0.1
            bd.topAir = val1
            bd.topAirPct = self._rangePercent(bd.topAir, self.config.topAirMin, self.config.topAirMax)
            bd.botAir = val2
            bd.botAirPct = self._rangePercent(bd.botAir, self.config.botAirMin, self.config.botAirMax)

        # Water Temp / O2
        req = requests.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,18,0,0,4,2")
        val = self._parseXml(req.text)
        if val is not None:
            val1 = int(f"{val:0{8}x}"[0:4], 16)
            val2 = int(f"{val:0{8}x}"[4:8], 16)

            bd.waterTemp = self._regressTemp(val1)

            # Check for out of wood
            if bd.waterTemp <= self.config.shutdownTemp and bd.o2 >= self.config.shutdownO2:
                bd.shutdown = True

            bd.o2 = self._regressO2(val2)

            # Check for first run
            if self._firstFun:
                self._lastO2s = np.full(shape=(self._slopeArrayLen,), fill_value=bd.o2, dtype=np.float64)
                self._lastTemps = np.full(shape=(self._slopeArrayLen,), fill_value=bd.waterTemp, dtype=np.float64)
                self._firstFun = False

            self._addWaterTemp(bd.waterTemp)
            self._addO2(bd.o2)

        # Check wood
        waterSlope = self._slopeWater()
        o2Avg = self._avgO2()
        self.logger.debug(f"Temp slope: {waterSlope}")
        self.logger.debug(f"O2 Avg: {o2Avg}")
        if bd.shutdown:
            # Probably no wood
            bd.wood = False
        elif o2Avg < self.config.shutdownO2:
            # There should be wood
            bd.wood = True
        else:
            # O2 is high
            if waterSlope < 0.0 and bd.fan:
                bd.wood = False
            else:
                bd.wood = True

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
