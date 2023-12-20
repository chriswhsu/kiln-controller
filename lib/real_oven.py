import logging

from lib.heat_output import HeatOutput
from lib.kill_switch import KillSwitch
from lib.oven import Oven
from lib.temp_sensor import TempSensorReal

log = logging.getLogger(__name__)


class RealOven(Oven):

    def __init__(self, configuration):
        self.config = configuration
        if self.config.kill_switch_enabled:
            self.kill_switch = KillSwitch(self.config)

        self.output = HeatOutput(self.config)
        self.complete()

        # call parent init
        log.info("Starting real oven...")
        self.is_simulation = False

        super().__init__(configuration)

    def create_temp_sensor(self):
        self.temp_sensor = TempSensorReal()
        self.temp_sensor.start()

    def complete(self):
        self.output.cool(0)
        super().complete()

    def abort(self):
        self.output.cool(0)
        super().abort()

    def stop(self):
        self.output.cool(0)
        super().stop()


    # get actual temperature from sensor.
    def update_temperature(self):
        self.temperature = self.temp_sensor.temperature + self.config.thermocouple_offset

    def apply_heat(self, pid):
        heat_on = float(self.time_step * pid)
        heat_off = float(self.time_step * (1 - pid))

        self.heat = 0.0
        if heat_on > 0:
            self.heat = 1.0

        if heat_on:
            self.output.heat(heat_on)
        if heat_off:
            self.output.cool(heat_off)
