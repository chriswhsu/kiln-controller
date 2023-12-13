import logging
import time

import config
from lib.oven import Oven
from lib.temp_sensor import TempSensorSimulated

log = logging.getLogger(__name__)


class SimulatedOven(Oven):

    def __init__(self):
        self.element_to_oven_heat_transfer = 0
        self.heat_transfer_rate_to_environ = 0
        self.heat_energy = 0
        self.environ_temp = config.sim_t_env
        self.elem_heat_capacity = config.element_heat_capacity
        self.c_oven = config.oven_heat_capacity
        self.p_heat = config.oven_heating_power
        self.oven_resistance = config.thermal_res_oven_to_environ
        self.element_resistance = config.thermal_res_element_to_oven

        # set temps to the temp of the surrounding environment
        self.oven_temp = self.environ_temp  # deg F temp of oven
        self.element_temperature = self.environ_temp  # deg F temp of heating element

        log.info("SimulatedOven starting")

        super().__init__()

    def create_temp_sensor(self):
        self.temp_sensor = TempSensorSimulated()
        # Doesn't really do anything, but start anyway.
        self.temp_sensor.start()

    def apply_heat(self, pid):
        self.heat = max(0.0, round(float(self.time_step * pid), 2))

        self.heating_energy(pid)

        log.debug("simulation: -> %dW heater: %.0f -> %dW oven: %.0f -> %dW env" % (int(self.p_heat * pid),
                                                                                    self.element_temperature,
                                                                                    int(self.element_to_oven_heat_transfer),
                                                                                    self.oven_temp,
                                                                                    int(self.heat_transfer_rate_to_environ)))

        self.temp_changes()
        time.sleep(self.time_step)

    def update_temperature(self):
        # temperature is set directly on member variable, no need to query temp sensor.
        pass

    def heating_energy(self, pid):
        # using pid here simulates the element being on for
        # only part of the time_step
        self.heat_energy = self.p_heat * self.time_step * pid

    def temp_changes(self):
        log.info(f"heat_energy: {self.heat_energy}")
        # temperature change of heat element by heating
        self.element_temperature += self.heat_energy / self.elem_heat_capacity

        # energy flux heat_el -> oven
        self.element_to_oven_heat_transfer = (self.element_temperature - self.oven_temp) / self.element_resistance

        # temperature change of oven and heating element
        self.oven_temp += self.element_to_oven_heat_transfer * self.time_step / self.c_oven
        self.element_temperature -= self.element_to_oven_heat_transfer * self.time_step / self.elem_heat_capacity

        # temperature change of oven by cooling to environment
        self.heat_transfer_rate_to_environ = (self.oven_temp - self.environ_temp) / self.oven_resistance
        self.oven_temp -= self.heat_transfer_rate_to_environ * self.time_step / self.c_oven

        self.temperature = round(self.oven_temp, 2)
        log.info(f"Set simulated oven temp to {self.temperature}")
