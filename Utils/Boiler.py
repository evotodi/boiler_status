from __future__ import annotations

__all__ = [
    "Boiler",
]

import logging
import re
import time
import zlib
from random import randint
import numpy as np
from scipy.stats import linregress
from typing import TYPE_CHECKING

import arrow
import requests
# noinspection PyPep8Naming
import xml.etree.ElementTree as ET
import pandas as pd

from Database.Database import Dbase
from Models.BoilerData import BoilerData, BoilerStatus
from Models.config import Config

if TYPE_CHECKING:
    # noinspection PyProtectedMember
    from scipy.stats._stats_mstats_common import LinregressResult
    from Database.Models.Event import EventData

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
    # noinspection PyArgumentList
    _lastXs = np.arange(stop=_slopeArrayLen)
    _lastO2s = np.full(shape=(_slopeArrayLen,), fill_value=6.0, dtype=np.float64)
    _lastTemps = np.full(shape=(_slopeArrayLen,), fill_value=180.0, dtype=np.float64)
    _firstFun = True
    _session = requests.Session()
    _lastWoodCheck: arrow.Arrow = arrow.get(0)
    _db: Dbase = None

    def __init__(self, db: Dbase):
        self.config = Config()
        self._db = db
        self._initBoilerData()

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

    def _initBoilerData(self):
        self.boilerData.lastBypassOpened = self._db.lastBypassOpened().ts
        self.logger.debug(f"Boiler bypass last opened: {self.boilerData.lastBypassOpened}")
        self.boilerData.lastWoodFilled = self._db.lastWoodFilled().ts
        self.logger.debug(f"Boiler wood last filled: {self.boilerData.lastWoodFilled}")

    def _login(self) -> bool:
        self._session = requests.Session()
        self._session.headers = {
            'Security-Hint': self._token,
            'Cache-Control': 'no-cache,no-store,must-revalidate',
            'Pragma': 'no-cache',
            'Content-Encoding': 'gzip',
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate',
            'App-Language': '1'
        }

        if self._secA1 is None:
            self._secA1 = randint(0, 4294967296)
        if self._secA2 is None:
            self._secA2 = randint(0, 4294967296)
        if self._secB1 is None:
            self._secB1 = randint(0, 4294967296)
        if self._secB2 is None:
            self._secB2 = randint(0, 4294967296)

        req1 = self._session.post(url=self.config.hmUrl, headers={'Security-Hint': 'p'}, data=f"UAMCHAL:3,4,{self._secA1},{self._secA2},{self._secB1},{self._secB2}")
        self.logger.debug(f"Login response = {req1.text}")
        ret = req1.text.split(',')
        if len(ret) == 3 and ret[0] == "700":
            pwToken = f"{self.config.passwd}+{ret[2]}"
            pwToken = pwToken[0:32]
            self.logger.debug(f"pwToken = {pwToken}")
            pwTokenCrc = zlib.crc32(pwToken.encode())
            iPWToken = pwTokenCrc ^ int(ret[2])
            self.logger.debug(f"iPWToken = {iPWToken}")
            iServerChallenge = (((self._secA1 ^ self._secA2) ^ self._secB1) ^ self._secB2) ^ int(ret[2])
            self.logger.debug(f"iServerChallenge = {iServerChallenge}")
            req2 = self._session.post(url=self.config.hmUrl, headers={'Security-Hint': f'{ret[1]}'}, data=f"UAMLOGIN:Web User,{iPWToken},{iServerChallenge}")
            self.logger.debug(f"Login response = {req2.text}")
            data = req2.text.split(',')
            if len(data) == 2 and data[0] == '700':
                self._token = data[1]
                return True
            else:
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

    def _parseXmlData(self, xml: str) -> ET.Element or None:
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            self.logger.error(f"Failed to parse: {xml}")
            return None

        return root

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

    def _slopeO2(self) -> float:
        lr = linregress(self._lastXs, self._lastO2s)  # type: LinregressResult
        self.logger.debug(f"O2 linear regression: {lr}")
        return lr.slope

    def _avgO2(self) -> float:
        return np.average(self._lastO2s)

    def _avgTemp(self) -> float:
        return np.average(self._lastTemps)

    def _updateBoiler(self):
        bd = self.boilerData
        if bd is None:
            bd = BoilerData()
            self.logger.debug("NEW BOILER DATA CREATED")

        if self._token is None:
            for _ in range(0, 4):
                if self._login():
                    break
            else:
                self.boilerData = None
                return

        bd.ts = arrow.utcnow()
        bd.lastWoodFilled = self._db.lastWoodFilled().ts
        bd.lastWoodFilledHuman = bd.lastWoodFilled.humanize()

        req = self._session.post(url=self.config.hmUrl, data="GETSTDG")
        if "Running" not in req.text:
            self.logger.info("Logging in after timeout")
            for _ in range(0, 4):
                if self._login():
                    break
            else:
                self.boilerData = None
                return

        """ Status """
        # Check for main page
        el = ET.Element("")
        for _ in range(0, 50):
            req = self._session.post(url=self.config.hmUrl, data="MSGGET:bm,-1")
            el = self._parseXmlData(req.text)
            self.logger.debug(f"Request Response: {req.text}")
            elType = el.get('type')
            if elType is not None and elType.strip().lower() == 's':
                elVal = el.find("./t[@id='0']").get('v')
                self.logger.debug(f"EL Val: {elVal}")
                if '*alarm*' in elVal.strip().lower():
                    self.logger.warning("Alarm status found")
                    break
                elif 'furnace status' not in elVal.strip().lower():
                    # Click up arrow and try again
                    self.logger.debug("Not status click up arrow")
                    self._session.post(url=self.config.hmUrl, data="MSGCLICK:bm,1,1")
                    time.sleep(2)
                    continue
                else:
                    # found status screen
                    self.logger.debug("Found status screen")
                    break
            else:
                # Click up arrow and try again
                self.logger.debug("Not data s click up arrow")
                self._session.post(url=self.config.hmUrl, data="MSGCLICK:bm,1,1")
                time.sleep(2)
                continue

        # Get furnace status
        self.logger.debug("Getting status")
        elVal = el.find("./t[@id='1']").get('v')
        statusTemporary = elVal.strip().lower()
        statusTemporary = re.sub(r'[^a-z0-9 ]', '', statusTemporary)
        try:
            bd.status = BoilerStatus(statusTemporary)
        except ValueError as ve:
            self.logger.error(ve)
            bd.status = BoilerStatus.ERROR
        self.logger.debug(f"DATA: Status: {bd.status}")

        """ Check heating cycle started """
        # First run check
        if bd.status == BoilerStatus.HEATING and self._firstFun:
            lastHeating = self._db.lastHeating()  # type: EventData
            self.logger.debug(f"Last Heating DB: {lastHeating}")

            if lastHeating is not None and lastHeating.value:
                bd.heatingStart = lastHeating.ts
            self.logger.debug(f"Heating start first run: {bd.heatingStart}")

        # Normal checks
        if bd.status == BoilerStatus.HEATING and bd.heatingStart is None:
            bd.heatingStart = arrow.utcnow()
            self._db.eventHeating(True, arrow.utcnow())
        elif bd.status != BoilerStatus.HEATING and bd.heatingStart is not None:
            bd.heatingStart = None
            self._db.eventHeating(False, arrow.utcnow())

        self.logger.debug(f"Heating start: {bd.heatingStart}")

        """ Fan """
        req = self._session.post(url=self.config.hmUrl, data="GETVARS:v0,130,0,0,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.fan = True
            else:
                bd.fan = False
            self.logger.debug(f"DATA: Fan: {bd.fan}")

        """ Shutdown """
        req = self._session.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,130,0,1,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.shutdown.value = False
            else:
                bd.shutdown.value = True

            if bd.shutdown.changed:
                self._db.eventShutdown(bd.shutdown.value)

            self.logger.debug(f"DATA: Shutdown: {bd.shutdown.value}")

        """ Alarm Lt """
        req = self._session.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,130,0,2,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.alarmLt = True
            # else:
            #     bd.alarmLt = False
            self.logger.debug(f"DATA: Alarm LT: {bd.alarmLt}")

        """ Low Water """
        req = self._session.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,129,0,0,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.lowWater = False
            else:
                bd.lowWater = True
            self.logger.debug(f"DATA: Low Water: {bd.lowWater}")

        """ Bypass """
        req = self._session.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,129,0,1,1,1")
        val = self._parseXml(req.text)
        self.logger.debug(f"DATA: Bypass request resp = {req.text}  val = {val}")
        if val is not None:
            if val > 0:
                bd.bypass.value = False
            else:
                bd.bypass.value = True
                bd.lastBypassOpened = arrow.utcnow()

            if bd.bypass.changed:
                self._db.eventBypassOpened(bd.bypass.value)

            bd.lastBypassOpenedHuman = bd.lastBypassOpened.humanize()
            self.logger.debug(f"DATA: Bypass: {bd.bypass.value}")

        """ Cold Start """
        req = self._session.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,129,0,2,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.coldStart.value = True
            else:
                bd.coldStart.value = False

            if bd.coldStart.changed:
                self._db.eventColdStart(bd.coldStart.value)

            self.logger.debug(f"DATA: Cold Start: {bd.coldStart.value}")

        """ High Limit """
        req = self._session.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,129,0,3,1,1")
        val = self._parseXml(req.text)
        if val is not None:
            if val > 0:
                bd.highLimit = False
            else:
                bd.highLimit = True
            self.logger.debug(f"DATA: High Limit: {bd.highLimit}")

        """ Bot / Top Air """
        req = self._session.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,19,0,0,4,2")
        val = self._parseXml(req.text)
        if val is not None:
            val1 = float(int(f"{val:0{8}x}"[0:4], 16)) * 0.1
            val2 = float(int(f"{val:0{8}x}"[4:8], 16)) * 0.1
            bd.topAir = val1
            bd.topAirPct = self._rangePercent(bd.topAir, self.config.topAirMin, self.config.topAirMax)
            bd.botAir = val2
            bd.botAirPct = self._rangePercent(bd.botAir, self.config.botAirMin, self.config.botAirMax)
            self.logger.debug(f"DATA: Top Air: {bd.topAirPct}  Bottom Air: {bd.botAirPct}")

        """ Water Temp / O2 """
        req = self._session.post(url=self.config.hmUrl, headers={'Security-Hint': self._token}, data="GETVARS:v0,18,0,0,4,2")
        val = self._parseXml(req.text)
        if val is not None:
            val1 = int(f"{val:0{8}x}"[0:4], 16)
            val2 = int(f"{val:0{8}x}"[4:8], 16)
            self.logger.debug(f"DATA: Water Temp: {val1}")
            self.logger.debug(f"DATA: O2: {val2}")

            bd.waterTemp = self._regressTemp(val1)
            self.logger.debug(f"DATA: Water Temp regress: {bd.waterTemp}")

            # # Check for out of wood
            # if bd.waterTemp <= self.config.shutdownTemp and bd.o2 >= self.config.shutdownO2:
            #     bd.shutdown = True

            bd.o2 = self._regressO2(val2)
            self.logger.debug(f"DATA: O2 regress: {bd.o2}")

            # Check for first run
            if self._firstFun:
                self._lastO2s = np.full(shape=(self._slopeArrayLen,), fill_value=bd.o2, dtype=np.float64)
                self._lastTemps = np.full(shape=(self._slopeArrayLen,), fill_value=bd.waterTemp, dtype=np.float64)

            self._addWaterTemp(bd.waterTemp)
            self._addO2(bd.o2)

        if self._firstFun and bd.status == BoilerStatus.HEATING:
            bd.heatingStart = arrow.utcnow().shift(minutes=-(self.config.woodEmptyCheckMins + 1)).replace(second=0)

        """ Calc Values"""
        bd.waterSlope = self._slopeWater()
        bd.tempAvg = self._avgTemp()
        bd.o2Slope = self._slopeO2()
        bd.o2Avg = self._avgO2()
        self.logger.debug(f"Temp slope: {bd.waterSlope}")
        self.logger.debug(f"Temp Avg: {bd.tempAvg}")
        self.logger.debug(f"O2 slope: {bd.o2Slope}")
        self.logger.debug(f"O2 Avg: {bd.o2Avg}")

        """ Check Condensing """
        if bd.tempAvg <= self.config.condensingTemp:
            bd.condensing = True
        else:
            bd.condensing = False
        self.logger.debug(f"Condensing: {bd.condensing}")

        """ Check wood """
        self._calcNextWoodFill()

        if not bd.bypass:  # Bypass closed
            self.logger.debug("Wood Check Bypass Closed")
            if arrow.utcnow().shift(minutes=-self.config.woodEmptyCheckMins).replace(second=0) > self._lastWoodCheck:
                self.logger.debug("Time to check wood")
                if bd.shutdown:
                    self.logger.warning("Wood off by shutdown")
                    bd.woodEmpty = True
                    bd.woodLow = True
                elif bd.status == BoilerStatus.LOW_TEMP:
                    self.logger.warning("Wood off by low temp")
                    bd.woodEmpty = True
                    bd.woodLow = True
                elif bd.o2Avg >= self.config.woodEmptyO2 and bd.waterSlope <= 0.0 and bd.condensing and bd.status == BoilerStatus.HEATING:
                    self.logger.warning("Wood off by condensing and high o2")
                    bd.woodEmpty = True
                    bd.woodLow = True
                elif bd.status == BoilerStatus.LOW_TEMP:
                    self.logger.warning("Wood off by low temperature")
                    bd.woodEmpty = True
                    bd.woodLow = True

                # Update last wood check
                self._lastWoodCheck = arrow.utcnow()

            # Check wood low
            if bd.o2Avg >= self.config.woodLowO2 and \
                    bd.waterSlope <= 0.0 and \
                    not bd.condensing and \
                    bd.status == BoilerStatus.HEATING and \
                    arrow.utcnow().shift(minutes=-self.config.woodLowHeatingMins).replace(second=0) > bd.lastWoodFilled:

                if arrow.utcnow().shift(minutes=-self.config.woodLowHeatingMins).replace(second=0) > bd.heatingStart or self._firstFun:
                    # High O2 and cooling-off while heating for some time means low wood
                    bd.woodLow = True
                    self.logger.debug("Wood low")
                else:
                    self.logger.debug("Wood low. Not set because it is not time yet")
            elif arrow.utcnow() > self._calcNextWoodFill():
                bd.woodLow = True
                self.logger.debug("Wood low by time")

        else:  # Bypass open
            self.logger.debug("Wood Check Bypass Open")
            bd.woodEmpty = False
            bd.woodLow = False
            # Update last wood check plus some extra time
            self._lastWoodCheck = arrow.utcnow().shift(minutes=+self.config.bypassOpenedWoodCheckMins)
        self.logger.debug(f"Wood: Empty = {bd.woodEmpty} Low = {bd.woodLow}")

        if bd.heatingStart is not None:
            self.logger.debug(f"Heating Start: {bd.heatingStart.format()}")
        else:
            self.logger.debug(f"Heating Start: None")

        """ Check Timer Cycle """
        if bd.status == BoilerStatus.IDLE and bd.fan and not bd.bypass:
            bd.status = BoilerStatus.TIMER_CYCLE

        """ Check Alarm Light """
        if bd.status not in [BoilerStatus.ERROR, BoilerStatus.NONE, BoilerStatus.LOW_TEMP, BoilerStatus.OFFLINE]:
            bd.alarmLt = False

        """ Finish """
        self.lastUpdate = arrow.utcnow()
        self.logger.info(f"Boiler updated. < {self.lastUpdate} >")
        self.logger.info(f"Boiler Data: {bd}")
        self.boilerData = bd
        self._session.close()

        """ First run done """
        if self._firstFun:
            self._firstFun = False

    def _calcNextWoodFill(self) -> arrow.Arrow:
        # Read sqlite query results into a pandas DataFrame
        df = pd.read_sql_query(f"SELECT ts as ds FROM event WHERE eventType == 'wood_filled' ORDER BY id DESC LIMIT {self.config.woodCalcLimit}", self._db.connection)

        # Add a y column
        df.insert(1, 'y', 0, True)

        # Convert column ds to datetimes
        for idx, row in df.iterrows():
            df.loc[idx, 'ds'] = arrow.get(row['ds']).naive

        df['ds'] = pd.DatetimeIndex(df['ds'])

        # Convert y to floats
        df = df.astype({"y": float})

        # Calculate total seconds between events
        for idx, row in df.iterrows():
            if idx != 0:
                cur = arrow.get(row['ds'])
                # noinspection PyTypeChecker
                prev = arrow.get(df.iloc[idx - 1]['ds'])
                secs = (prev - cur).total_seconds()
                df.loc[idx, 'y'] = secs / 60

        # Index 0's y value
        df.loc[0, 'y'] = df.loc[1, 'y']

        # Drop the upper and lower 1% outliers
        df_sub = df.loc[:, ['ds', 'y']]
        lim = np.logical_and(df_sub['y'] < df_sub['y'].quantile(0.99),
                             df_sub['y'] > df_sub['y'].quantile(0.01))

        df.loc[:, ['y']] = df_sub.where(lim, np.nan)
        df.dropna(inplace=True)

        # Calculate the mean of y
        meanMins = np.mean(df.loc[:, 'y'])

        # Get last wood fill
        lastFill = self._db.lastWoodFilled().ts
        # Shift if forward meanMins
        nextFill = lastFill.shift(minutes=meanMins)
        # Offset next fill by woodLowCalcOffsetHours
        nextFill = nextFill.shift(hours=self.config.woodLowCalcOffsetHours)

        self.logger.debug(f"Next calculated fill: {nextFill}")

        return nextFill

    def getData(self) -> BoilerData:
        if arrow.utcnow().shift(seconds=-self.config.updateBoilerSeconds) > self.lastUpdate:
            self._updateBoiler()
        self.logger.info(f"Boiler last updated at {self.lastUpdate}")

        return self.boilerData

    def timeToUpdate(self) -> bool:
        if arrow.utcnow().shift(seconds=-self.config.updateBoilerSeconds) > self.lastUpdate:
            return True

        return False

    def getOfflineData(self) -> BoilerData:
        bd = BoilerData()
        bd.ts = arrow.utcnow()
        bd.status = BoilerStatus.OFFLINE
        bd.coldStart = False
        bd.highLimit = False
        bd.alarmLt = True
        bd.lowWater = False
        bd.fan = False
        bd.shutdown = True
        bd.waterTemp = False
        bd.woodEmpty = False
        bd.woodLow = False
        self.lastUpdate = arrow.utcnow()

        return bd

    def woodFilled(self):
        self.boilerData.woodLow = False
        self.boilerData.woodEmpty = False
