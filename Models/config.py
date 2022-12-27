__all__ = [
    "Config",
]

from pydantic import BaseModel

class Config(BaseModel):
    hmUrl = "http://192.168.12.220/AJAX"
    passwd = "heatmaster"

    mqttServer: str = 'mqtt'
    mqttUser: str = 'admin'
    mqttPasswd: str = 'Isabelle2014'
    mqttBaseTopic: str = 'homie/'

    updateBoilerSeconds: int = 15
    shutdownTemp: float = 119.0
    shutdownO2: float = 10.0
    noWoodWaterTemp: float = 140.0
    noWoodCheckMins: int = 20

    botAirMin: float = 0.0
    botAirMax: float = 100.0
    topAirMin: float = 50.0
    topAirMax: float = 75.0
