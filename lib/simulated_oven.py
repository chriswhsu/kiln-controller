import logging
from gevent import sleep
from lib.oven import Oven
from lib.temp_sensor import TempSensorSimulated

log = logging.getLogger(__name__)


class SimulatedOven(Oven):

    def __init__(self, configuration):
        self.config = configuration
        self.element_to_oven_heat_transfer = 0
        self.heat_transfer_rate_to_environ = 0
        self.heat_energy = 0
        self.environ_temp = self.config.simulated_room_temp
        self.elem_heat_capacity = self.config.element_heat_capacity
        self.c_oven = self.config.oven_heat_capacity
        self.p_heat = self.config.oven_heating_power
        self.oven_resistance = self.config.thermal_res_oven_to_environ
        self.element_resistance = self.config.thermal_res_element_to_oven

        # set temps to the temp of the surrounding environment
        self.element_temperature = self.environ_temp  # deg F temp of heating element
        log.info("SimulatedOven starting")

        super().__init__(configuration)

        self.temperature = configuration.simulated_room_temp
        self.is_simulation = True

    def create_temp_sensor(self):
        self.temp_sensor = TempSensorSimulated(self.config)
        # Doesn't really do anything, but start anyway.
        self.temp_sensor.start()

    def stop(self):
        self.heat_energy = 0
        super().stop()

    def apply_heat(self, pid):
        # Determine the proportion of the time step the heater is on
        self.heat = max(0.0, float(self.time_step * pid))

        # Calculate the heating energy based on the proportion of time the heater is on
        self.heat_energy = self.p_heat * self.heat

        log.info(
                f"simulation: -> {self.p_heat * pid:.2f}W heater: {self.element_temperature:.2f} -> "
                f"{self.element_to_oven_heat_transfer:.2f}W oven: {self.temperature:.2f} -> "
                f"{self.heat_transfer_rate_to_environ:.2f}W env"
        )

        sleep(self.time_step)

    def update_temperature(self):
        # temperature is set directly on member variable, no need to query temp sensor.
        # just simulate the change
        self.simulate_temp_changes()

    def simulate_temp_changes(self):
        oven_temp = self.temperature
        log.info(f"Initial oven_temp: {oven_temp}")
        log.debug(f"Initial heat_energy: {self.heat_energy}")
        log.debug(f"Element Heat Capacity: {self.elem_heat_capacity}")

        # temperature change of heat element by heating
        self.element_temperature += self.heat_energy / self.elem_heat_capacity
        log.debug(f"Element temperature after heating: {self.element_temperature}")

        # energy flux heat_el -> oven
        self.element_to_oven_heat_transfer = (self.element_temperature - oven_temp) / self.element_resistance
        log.debug(f"Energy flux from element to oven: {self.element_to_oven_heat_transfer}")

        # temperature change of oven and heating element
        oven_temp += self.element_to_oven_heat_transfer * self.time_step / self.c_oven
        self.element_temperature -= self.element_to_oven_heat_transfer * self.time_step / self.elem_heat_capacity
        log.debug(f"Oven temperature after energy flux: {oven_temp}")
        log.debug(f"Element temperature after energy flux: {self.element_temperature}")

        # temperature change of oven by cooling to environment
        self.heat_transfer_rate_to_environ = (oven_temp - self.environ_temp) / self.oven_resistance
        oven_temp -= self.heat_transfer_rate_to_environ * self.time_step / self.c_oven
        log.debug(f"Heat transfer rate to environment: {self.heat_transfer_rate_to_environ}")
        log.debug(f"Oven temperature after adjusting for environment: {oven_temp}")

        self.temperature = round(oven_temp, 2)
        log.info(f"Final simulated oven temperature: {self.temperature}")
