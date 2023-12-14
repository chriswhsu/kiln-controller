import datetime
import json
import logging
import threading
import time

import config
from lib.pid import PID

log = logging.getLogger(__name__)


class Oven(threading.Thread):
    # parent oven class. this has all the common code for either a real or simulated oven

    def __init__(self):
        threading.Thread.__init__(self)
        self.kill_switch = None
        self.startat = 0
        self.pid = PID()
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

    def _reset_oven_state(self):
        self.cost = 0
        self.runtime = 0
        self.total_time = 0
        self.start_time = None

    def complete(self):
        self.state = "COMPLETE"
        self.target = 0
        self.heat = 0

    def abort(self):
        self.state = "ABORTED"
        self.target = 0
        self.heat = 0

    def stop(self):
        self.state = "STOP"
        self.target = 0
        self.heat = 0

    def create_temp_sensor(self):
        raise NotImplementedError("This method should be overridden in child classes")

    def run_profile(self, profile, startat=0):
        self._reset_oven_state()  # Reset state at the start of a new run

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
                f"temp={self.temperature:.2f}, target={self.target:.2f}, pid_output={pid_output:.2f}, "
                f"heat_on={heat_on:.2f}, heat_off={heat_off:.2f}, run_time={self.runtime:.1f}"
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
        self.target = self.profile.get_target_temperature(self.runtime)

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
            log.info("total cost = %s%.2f" % (config.currency_type, self.cost))
            self.complete()

    def update_cost(self):
        if self.heat:
            cost = (config.kwh_rate * config.kw_elements) * (self.heat / 3600)
        else:
            cost = 0
        self.cost += cost

    def get_status(self):

        state = {
            'cost': round(self.cost, 2),
            'runtime': round(self.runtime, 2),
            'temperature': self.temperature,
            'target': self.target,
            'state': self.state,
            'heat': round(self.heat, 2),
            'total_time': self.total_time,
            'profile': self.profile.name if self.profile else None}
        return state

    def save_status(self):
        with open(config.automatic_restart_state_file, 'w', encoding='utf-8') as f:
            json.dump(self.get_status(), f, ensure_ascii=False, indent=4)

    def update_temperature(self):
        # Placeholder method - overridden in child classes
        raise NotImplementedError("This method should be overridden in child classes")

    def run(self):
        while True:
            if self.state == "IDLE":
                time.sleep(1)
                self.update_temperature()
            elif self.state == "RUNNING":
                self.update_temperature()
                self.update_cost()
                self.kiln_must_catch_up()
                self.update_runtime()
                self.update_target_temp()
                self.determine_heat()
                self.reset_if_emergency()
                self.reset_if_schedule_ended()
            elif self.state == "COMPLETE":
                log.info("state completed")
                time.sleep(1)
                self.update_runtime()
                self.update_temperature()
