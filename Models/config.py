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
