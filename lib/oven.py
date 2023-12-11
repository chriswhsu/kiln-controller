import datetime
import json
import logging
import os
import threading
import time

import config
import output
from lib.killSwitch import KillSwitch
from lib.output import Output
from lib.pid import PID
from lib.profile import Profile
from lib.tempSensor import TempSensorSimulated, TempSensorReal

log = logging.getLogger(__name__)


class Oven(threading.Thread):
    # parent oven class. this has all the common code for either a real or simulated oven

    def __init__(self):
        threading.Thread.__init__(self)
        self.kill_switch = None
        self.ovenwatcher = None
        self.startat = 0
        self.pid = PID(kp=config.pid_kp, ki=config.pid_ki, kd=config.pid_kd)
        # heating or not?
        self.heat = 0
        self.target = 0
        self.start_time = None
        self.runtime = 0
        self.total_time = 0
        self.profile = None
        self.state = "IDLE"
        self.cost = 0
        self.temp_sensor = None
        self.daemon = True
        self.temperature = 0
        self.time_step = config.sensor_time_wait
        self.create_temp_sensor()

        # start thread
        self.start()

    def _common_reset_abort_logic(self, state):
        self.cost = 0
        self.state = state
        self.profile = None
        self.start_time = 0
        self.runtime = 0
        self.total_time = 0
        self.target = 0
        self.heat = 0
        self.pid = PID( kp=config.pid_kp, ki=config.pid_ki, kd=config.pid_kd)

    def complete(self):
        self._common_reset_abort_logic("COMPLETE")

    def abort(self):
        self._common_reset_abort_logic("ABORTED")

    def stop(self):
        self._common_reset_abort_logic("STOPPED")

    def create_temp_sensor(self):
        raise NotImplementedError("This method should be overridden in child classes")

    def run_profile(self, profile, startat=0):
        self.complete()

        self.startat = startat * 60
        self.runtime = self.startat
        self.start_time = datetime.datetime.now() - datetime.timedelta(seconds=self.startat)
        self.profile = profile
        self.total_time = profile.get_duration()
        self.state = "RUNNING"
        log.info("Running schedule %s starting at %d minutes" % (profile.name, startat))
        log.info("Starting")

    def determine_heat(self):
        # Compute the PID output for the current target and temperature
        pid_output = self.pid.compute(self.target, self.temperature)

        # Apply heating or cooling based on PID output.
        self.apply_heat(pid_output)
        self.log_heating(pid_output)

    def apply_heat(self, pid_output):
        # Placeholder method - overridden in child classes
        raise NotImplementedError("This method should be overridden in child classes")

    def log_heating(self, pid_output):
        # Log the details of the
        # heating/cooling process
        # This is a common method that might be same for both simulated and real ovens
        heat_on = float(self.time_step * pid_output)
        heat_off = float(self.time_step * (1 - pid_output))

        log.info(
                "temp=%.2f, target=%.2f, pid_output=%.2f, heat_on=%.2f, heat_off=%.2f, run_time=%d" %
                (self.temperature, self.target, pid_output, heat_on, heat_off, self.runtime)
        )

    def kiln_must_catch_up(self):
        if config.kiln_must_catch_up:
            temperature_difference = self.target - self.temperature
            if temperature_difference > config.profile_pause_window:
                log.info("kiln must catch up, too cold")
                self.start_time = datetime.datetime.now() - datetime.timedelta(milliseconds=self.runtime * 1000)

    def update_runtime(self):
        runtime_delta = datetime.datetime.now() - self.start_time
        self.runtime = max(0.0, round(runtime_delta.total_seconds(), 2))

    def update_target_temp(self):
        self.target = round(self.profile.get_target_temperature(self.runtime), 2)

    def reset_if_emergency(self):
        # reset if the temperature is way TOO HOT, or other critical errors detected
        if self.temperature >= config.emergency_shutoff_temp:
            log.error("Emergency!!! Temperature too high.")
            self.abort()
            if self.kill_switch:
                log.error("Activating kill switch. System will power off.")
                self.kill_switch.kill()  # Activate the kill switch as the last action

    def reset_if_schedule_ended(self):
        if self.runtime > self.total_time:
            log.info("schedule ended, shutting down")
            log.info("total cost = %s%.2f" % (output.currency_type, self.cost))
            self.complete()

    def update_cost(self):
        if self.heat:
            cost = (output.kwh_rate * output.kw_elements) * (self.heat / 3600)
        else:
            cost = 0
        self.cost += cost

    def get_state(self):

        state = {
            'cost': round(self.cost, 2),
            'runtime': round(self.runtime, 2),
            'temperature': self.temperature,
            'target': self.target,
            'state': self.state,
            'heat': self.heat,
            'total_time': self.total_time,
            'profile': self.profile.name if self.profile else None        }
        return state

    def save_state(self):
        with open(config.automatic_restart_state_file, 'w', encoding='utf-8') as f:
            json.dump(self.get_state(), f, ensure_ascii=False, indent=4)

    @staticmethod
    def state_file_is_old():
        # returns True is state files is older than 15 mins default
        #         False if younger
        #         True if state file cannot be opened or does not exist

        if os.path.isfile(config.automatic_restart_state_file):
            state_age = os.path.getmtime(config.automatic_restart_state_file)
            now = time.time()
            minutes = (now - state_age) / 60
            if minutes <= config.automatic_restart_window:
                return False
        return True

    def save_automatic_restart_state(self):
        # only save state if the feature is enabled
        if config.automatic_restarts:
            self.save_state()

    def should_i_automatic_restart(self):
        # only automatic restart if the feature is enabled
        if not config.automatic_restarts:
            return False
        if self.state_file_is_old():
            log.info("automatic restart not possible. state file does not exist or is too old.")
            return False

        with open(config.automatic_restart_state_file) as infile:
            d = json.load(infile)
        if d["state"] != "RUNNING":
            log.info("automatic restart not possible. state = %s" % (d["state"]))
            return False
        return True

    def automatic_restart(self):
        with open(config.automatic_restart_state_file) as infile:
            d = json.load(infile)
        startat = d["runtime"] / 60
        filename = "%s.json" % (d["profile"])
        profile_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'storage', 'profiles', filename))

        log.info("automatically restarting profile = %s at minute = %d" % (profile_path, startat))
        with open(profile_path) as infile:
            profile_json = json.dumps(json.load(infile))
        profile = Profile(profile_json)
        self.run_profile(profile, startat=startat)
        self.cost = d["cost"]
        time.sleep(1)
        self.ovenwatcher.record(profile)

    def set_ovenwatcher(self, watcher):
        log.info("ovenwatcher set in oven class")
        self.ovenwatcher = watcher

    def update_temperature(self):
        pass

    def run(self):
        while True:
            if self.state == "IDLE":
                if self.should_i_automatic_restart():
                    self.automatic_restart()
                time.sleep(1)
                continue
            if self.state == "RUNNING":
                self.update_temperature()
                self.update_cost()
                self.save_automatic_restart_state()
                self.kiln_must_catch_up()
                self.update_runtime()
                self.update_target_temp()
                self.determine_heat()
                self.reset_if_emergency()
                self.reset_if_schedule_ended()


class SimulatedOven(Oven):

    def __init__(self):
        self.element_to_oven_heat_transfer = None
        self.heat_transfer_rate_to_environ = None
        self.heat_energy = None
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
        self.temp_changes()

        log.info("simulation: -> %dW heater: %.0f -> %dW oven: %.0f -> %dW env" % (int(self.p_heat * pid),
                                                                                   self.element_temperature,
                                                                                   int(self.element_to_oven_heat_transfer),
                                                                                   self.oven_temp,
                                                                                   int(self.heat_transfer_rate_to_environ)))

        time.sleep(self.time_step)

    def update_temperature(self):
        # temperature is set directly on member variable, no need to query temp sensor.
        pass

    def heating_energy(self, pid):
        # using pid here simulates the element being on for
        # only part of the time_step
        self.heat_energy = self.p_heat * self.time_step * pid

    def temp_changes(self):
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


class RealOven(Oven):

    def __init__(self):

        if config.kill_switch_enabled:
            self.kill_switch = KillSwitch()

        self.output = Output()
        self.complete()

        # call parent init
        log.info("Starting real oven...")
        Oven.__init__(self)

    def create_temp_sensor(self):
        self.temp_sensor = TempSensorReal()
        self.temp_sensor.start()

    def complete(self):
        self.end_things()

    def abort(self):
        self.end_things()

    def stop(self):
        self.end_things()

    def end_things(self):
        log.info("Shutting down oven.")
        super().complete()
        self.output.cool(0)

    # get actual temperature from sensor.
    def update_temperature(self):
        self.temperature = self.temp_sensor.temperature + config.thermocouple_offset

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
