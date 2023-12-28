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

    homiePublishStatusSeconds: int = 15  # How often to publish the homie status
    updateBoilerSeconds: int = 15  # How often to update the boiler data in seconds
    shutdownTemp: float = 119.0  # Temp where boiler shuts down
    woodEmptyO2: float = 15.0  # O2 percent when no wood in boiler or wood is not burning
    woodLowO2: float = 10.0  # O2 percent when just coals are in boiler
    condensingTemp: float = 148.0  # Temperature where creosote begins to form is 145
    woodEmptyCheckMins: int = 20  # How many minutes between wook checks
    woodLowHeatingMins: int = 60  # How many minutes heating cycle need to run before low wood check
    bypassOpenedWoodCheckMins: int = 30  # How many minutes to wait before checking if wood is low or empty

    # These should match the boiler settings
    botAirMin: float = 0.0
    botAirMax: float = 100.0
    topAirMin: float = 50.0
    topAirMax: float = 75.0
