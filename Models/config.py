__all__ = [
    "Config",
]

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field
from urllib.parse import urljoin

class Config(BaseSettings):
    model_config = SettingsConfigDict(env_ignore_empty=True)

    hmUrlBase: str = Field(alias='HM_URL')
    hmPassword: str = Field(alias='HM_PASSWORD', default="heatmaster")

    mqttServer: str = Field(alias='MQTT_BROKER')
    mqttUser: str = Field(alias='MQTT_USER')
    mqttPasswd: str = Field(alias='MQTT_PASSWORD')
    mqttBaseTopic: str = Field(alias='MQTT_BASE_TOPIC', default='homie/')

    homiePublishStatusSeconds: int = Field(alias='PUBLISH_STATUS_SECS', default=15)  # How often to publish the homie status
    updateBoilerSeconds: int = Field(alias='UPDATE_BOILER_SECS', default=15)  # How often to update the boiler data in seconds
    shutdownTemp: float = Field(alias='SHUTDOWN_TEMP', default=119.0)  # Temp where boiler shuts down
    woodEmptyO2: float = Field(alias='WOOD_EMPTY_O2', default=15.0)  # O2 percent when no wood in boiler or wood is not burning
    woodLowO2: float = Field(alias='WOOD_LOW_O2', default=10.0)  # O2 percent when just coals are in boiler
    condensingTemp: float = Field(alias='CONDENSING_TEMP', default=148.0)  # Temperature where creosote begins to form is 145
    woodEmptyCheckMins: int = Field(alias='WOOD_EMPTY_CHECK_MINS', default=20)  # How many minutes between wook checks
    woodLowHeatingMins: int = Field(alias='WOOD_LOW_HEATING_MINS', default=60)  # How many minutes heating cycle need to run before low wood check
    bypassOpenedWoodCheckMins: int = Field(alias='BYPASS_OPENED_WOOD_CHECK_MINS', default=30)  # How many minutes to wait before checking if wood is low or empty
    bypassWoodFilledMins: int = Field(alias='BYPASS_WOOD_FILLED_MINS', default=120)  # How many minutes between bypass open to count as a wood fill event
    woodLowCalcOffsetHours: int = Field(alias='WOOD_LOW_CALC_OFFSET_HRS', default=-3)  # How many hours to offset the calculated next wood fill needed
    woodCalcLimit: int = Field(alias='WOOD_CALC_LIMIT', default=20)  # Select the last n wood fills for calc

    # These should match the boiler settings
    botAirMin: float = Field(alias='BOTTOM_AIR_MIN', default=0.0)
    botAirMax: float = Field(alias='BOTTOM_AIR_MAX', default=100.0)
    topAirMin: float = Field(alias='TOP_AIR_MIN', default=50.0)
    topAirMax: float = Field(alias='TOP_AIR_MAX', default=75.0)

    @computed_field
    @property
    def hmUrl(self) -> str:
        return urljoin(self.hmUrlBase, "/AJAX")
