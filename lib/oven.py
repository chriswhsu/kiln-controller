import datetime
import logging
import time

from gevent import sleep, Greenlet

from lib.pid import PID

log = logging.getLogger(__name__)


class Oven(Greenlet):
    # parent oven class. this has all the common code for either a real or simulated oven

    def __init__(self, configuration):
        super(Oven, self).__init__()
        self.config = configuration
        self.is_simulation = None
        self.startat = 0
        self.pid = PID(configuration=self.config)
        # heating or not?
        self.heat = 0
        self.target = 0
        self.start_time = None
        self.time_stamp = 0
        self.total_time = 0
        self.profile = None
        self.state = "IDLE"
        self.cost = 0
        self.temp_sensor = None
        self.daemon = True
        self.temperature = 0
        self.time_step = self.config.sensor_time_wait
        # used for safety check to make sure if heat is being applied
        # we are close to temp or temp is increasing.
        self.previous_temperature = None
        self.stable_temp_start_time = None

        self.create_temp_sensor()
        self._running = True

        # start thread
        self.start()

    def die(self):
        self._running = False

    def _reset_oven_state(self):
        self.cost = 0
        self.time_stamp = 0
        self.total_time = 0
        self.start_time = None

    def complete(self):
        log.info('complete-->')
        self.state = "COMPLETE"
        self.target = 0
        self.heat = 0

    def abort(self):
        log.info('abort-->')
        self.state = "ABORTED"
        self.target = 0
        self.heat = 0

    def stop(self):
        log.info('stop-->')
        self.state = "IDLE"
        self.target = 0
        self.heat = 0

    def create_temp_sensor(self):
        raise NotImplementedError("This method should be overridden in child classes")

    def run_profile(self, profile, startat=0):
        self._reset_oven_state()  # Reset state at the start of a new run

        self.startat = startat * 60
        self.time_stamp = self.startat
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
                f"heat_on={heat_on:.2f}, heat_off={heat_off:.2f}, run_time={self.time_stamp:.1f}"
        )

    def kiln_must_catch_up(self):
        if self.config.kiln_must_catch_up:
            temperature_difference = self.target - self.temperature
            if temperature_difference > self.config.profile_pause_window:
                log.info("kiln must catch up, too cold")
                self.start_time = datetime.datetime.now() - datetime.timedelta(milliseconds=self.time_stamp * 1000)

    def update_runtime(self):
        runtime_delta = datetime.datetime.now() - self.start_time
        self.time_stamp = max(0.0, round(runtime_delta.total_seconds(), 2))

    def update_target_temp(self):
        self.target = self.profile.get_target_temperature(self.time_stamp)

    def reset_if_emergency(self):
        # reset if the temperature is way TOO HOT, or other critical errors detected
        if self.temperature >= self.config.emergency_shutoff_temp:
            log.error("Emergency!!! Temperature too high.")
            self.abort()

    def reset_if_schedule_ended(self):
        if self.time_stamp > self.total_time:
            log.info("schedule ended, shutting down")
            log.info("total cost = %s%.2f" % (self.config.currency_type, self.cost))
            self.complete()

    def update_cost(self):
        if self.heat:
            cost = (self.config.kwh_rate * self.config.kw_elements) * (self.heat / 3600)
        else:
            cost = 0
        self.cost += cost

    def get_status(self):

        state = {
            'cost': round(self.cost, 2),
            'time_stamp': round(self.time_stamp, 2),
            'temperature': self.temperature,
            'target': self.target,
            'state': self.state,
            'heat': round(self.heat, 2),
            'total_time': self.total_time,
            'profile': self.profile.name if self.profile else None,
            'is_simulation': self.is_simulation}
        log.info(state)
        return state

    def update_temperature(self):
        # Placeholder method - overridden in child classes
        raise NotImplementedError("This method should be overridden in child classes")

    def check_temperature_increase(self):
        # Fetch current time
        current_time = time.monotonic()

        # Log current time, temperature and target temperature
        log.debug(f"*******Current time: {current_time}, temp: {self.temperature}, target: {self.target}")

        # Check if heat is being applied and temperature is 50 degrees below target
        if self.heat > 0 and self.temperature < self.target - self.config.abort_temp_diff_threshold:
            log.debug("*****below target")

            # Verify if current temperature is not increasing compared to previous temperature
            if self.previous_temperature is not None and self.temperature <= self.previous_temperature + self.config.temp_increase_threshold:
                log.debug(f"***not increasing temperature")

                # If it's the first time we notice that the temperature is not increasing
                if self.stable_temp_start_time is None:
                    self.stable_temp_start_time = current_time

                # If the temperature has not increased for the time window defined (e.g., 2 minutes)
                elif (current_time - self.stable_temp_start_time) >= self.config.abort_threshold_minutes * 60:
                    # Log an error message and abort if the temperature is not increasing for the given threshold time
                    log.error(
                            F'Temperature more than {self.config.abort_temp_diff_threshold} degrees below the target for over {self.config.abort_threshold_minutes} minutes during heating, aborting!')
                    self.abort()
            else:  # if temperature is increasing, reset stable_temp_start_time
                log.debug("****temp increasing")
                self.stable_temp_start_time = None

        else:  # if not heating or temperature is not 50 degrees below target, reset stable_temp_start_time
            log.debug(f"*****temperature on target or not heating.")
            self.stable_temp_start_time = None

        # Update previous temperature for the next function call
        self.previous_temperature = self.temperature

    def _run(self):
        while self._running:
            if self.state == "IDLE":
                log.info(f"timestamp: {self.time_stamp}, state: {self.state}, temperature: {self.temperature}")
                sleep(self.config.idle_sample_time)
                self.update_temperature()
            elif self.state == "RUNNING":
                self.update_temperature()
                self.update_cost()
                self.kiln_must_catch_up()
                self.update_runtime()
                self.update_target_temp()
                self.determine_heat()
                self.check_temperature_increase()
                self.reset_if_emergency()
                self.reset_if_schedule_ended()
            elif self.state == "COMPLETE":
                log.info(f"runtime: {self.time_stamp}, state: {self.state}, temperature: {self.temperature}")
                sleep(self.config.idle_sample_time)
                self.update_runtime()
                self.update_temperature()
            else:
                sleep(self.config.idle_sample_time)
