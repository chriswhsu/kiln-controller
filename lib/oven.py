import threading
import time
import datetime
import logging
import json
import config
import os

from lib.KillSwitch import KillSwitch

log = logging.getLogger(__name__)


class DupLogger:
    """ A logger class with an integrated duplicate message filter. """

    def __init__(self):
        """ Initializes the logger with an integrated duplicate filter. """
        self.msgs = set()
        self.log = logging.getLogger(f"{__name__}.duplicateFree")
        self.log.addFilter(self.filter)

    def filter(self, record):
        # Filters the log record for duplicates.
        if record.msg not in self.msgs:
            self.msgs.add(record.msg)
            return True
        return False

    def get_logger(self):
        """
        Returns a reference to the logger.

        Returns:
            logging.Logger: The logger instance with an integrated duplicate filter.
        """
        return self.log


dup_log = DupLogger().get_logger()


class Output:
    def __init__(self):
        self.GPIO = None
        self.active = False
        self.load_libs()

    def load_libs(self):
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(config.gpio_heat, GPIO.OUT)
            self.active = True
            self.GPIO = GPIO
        except Exception as e:
            log.warning(f"Could not initialize GPIOs, oven operation will only be simulated: {e}")
            self.active = False

    def heat(self, sleep_for):
        self.GPIO.output(config.gpio_heat, self.GPIO.HIGH)
        time.sleep(sleep_for)

    def cool(self, sleep_for):
        # no active cooling, so sleep
        self.GPIO.output(config.gpio_heat, self.GPIO.LOW)
        time.sleep(sleep_for)


class TempSensor(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.temperature = 0
        self.bad_percent = 0
        self.time_step = config.sensor_time_wait
        self.noConnection = self.shortToGround = self.shortToVCC = self.unknownError = False

    def run(self):
        pass


class TempSensorSimulated(TempSensor):
    # not much here, just need to be able to set the temperature

    def __init__(self):
        TempSensor.__init__(self)


class TempSensorReal(TempSensor):
    # real temperature sensor thread that takes N measurements during the time_step

    def __init__(self):
        TempSensor.__init__(self)
        self.sleep_time = self.time_step / float(config.temperature_average_samples)
        self.bad_count = 0
        self.ok_count = 0
        self.bad_stamp = 0

        if config.max31855:
            log.info("init MAX31855")
            from lib.max31855 import MAX31855
            self.thermocouple = MAX31855(config.gpio_sensor_cs,
                                         config.gpio_sensor_clock,
                                         config.gpio_sensor_data,
                                         config.temp_scale)

        if config.max31856:
            log.info("init MAX31856")
            from lib.max31856 import MAX31856
            software_spi = {'cs': config.gpio_sensor_cs,
                            'clk': config.gpio_sensor_clock,
                            'do': config.gpio_sensor_data,
                            'di': config.gpio_sensor_di}
            self.thermocouple = MAX31856(tc_type=config.thermocouple_type,
                                         software_spi=software_spi,
                                         units=config.temp_scale,
                                         ac_freq_50hz=config.ac_freq_50hz,
                                         )

    def run(self):
        # use a moving average of config.temperature_average_samples across the time_step
        temps = []
        while True:
            # reset error counter if time is up
            if (time.time() - self.bad_stamp) > (self.time_step * 2):
                if self.bad_count + self.ok_count:
                    self.bad_percent = (self.bad_count / (self.bad_count + self.ok_count)) * 100
                else:
                    self.bad_percent = 0
                self.bad_count = 0
                self.ok_count = 0
                self.bad_stamp = time.time()

            temp = self.thermocouple.get()
            self.noConnection = self.thermocouple.noConnection
            self.shortToGround = self.thermocouple.shortToGround
            self.shortToVCC = self.thermocouple.shortToVCC
            self.unknownError = self.thermocouple.unknownError

            is_bad_value = self.noConnection | self.unknownError
            if not config.ignore_tc_short_errors:
                is_bad_value |= self.shortToGround | self.shortToVCC

            if not is_bad_value:
                temps.append(temp)
                if len(temps) > config.temperature_average_samples:
                    del temps[0]
                self.ok_count += 1

            else:
                log.error("Problem reading temp N/C:%s GND:%s VCC:%s ???:%s" % (self.noConnection, self.shortToGround, self.shortToVCC, self.unknownError))
                self.bad_count += 1

            if len(temps):
                self.temperature = self.get_avg_temp(temps)
            time.sleep(self.sleep_time)

    @staticmethod
    def get_avg_temp(temps, chop=25):

        # strip off chop percent from the beginning and end of the sorted temps then return the average of what is left

        chop = chop / 100
        temps = sorted(temps)
        total = len(temps)
        items = int(total * chop)
        temps = temps[items:total - items]
        return sum(temps) / len(temps)


class Oven(threading.Thread):
    # parent oven class. this has all the common code for either a real or simulated oven

    def __init__(self):
        threading.Thread.__init__(self)
        self.kill_switch = None
        self.ovenwatcher = None
        self.startat = 0
        self.pid = PID(ki=config.pid_ki, kd=config.pid_kd, kp=config.pid_kp)
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
        self.pid = PID(ki=config.pid_ki, kd=config.pid_kd, kp=config.pid_kp)

    def complete(self):
        self._common_reset_abort_logic("COMPLETE")

    def abort(self):
        self._common_reset_abort_logic("ABORTED")

    def stop(self):
        self._common_reset_abort_logic("STOPPED")

    def create_temp_sensor(self):
        pass

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

    def heat_then_cool(self):
        # Compute the PID output for the current target and temperature
        pid_output = self.pid.compute(self.target, self.temperature)

        # Apply heating or cooling based on PID output.
        # This method will be overridden in child classes.
        self.apply_heat(pid_output)

        # Log the heating or cooling process
        self.log_heating_cooling(pid_output)

    def apply_heat(self, pid_output):
        # Placeholder method - should be overridden in child classes
        raise NotImplementedError("This method should be overridden in child classes")

    def log_heating_cooling(self, pid_output):
        # Log the details of the heating/cooling process
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
            if temperature_difference > config.pid_control_window:
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
            log.info("total cost = %s%.2f" % (config.currency_type, self.cost))
            self.complete()

    def update_cost(self):
        if self.heat:
            cost = (config.kwh_rate * config.kw_elements) * (self.heat / 3600)
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
            'profile': self.profile.name if self.profile else None,
            'pid_stats': self.pid.pidstats,
        }
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
            dup_log.info("automatic restart not possible. state file does not exist or is too old.")
            return False

        with open(config.automatic_restart_state_file) as infile:
            d = json.load(infile)
        if d["state"] != "RUNNING":
            dup_log.info("automatic restart not possible. state = %s" % (d["state"]))
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
                self.heat_then_cool()
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


class Profile:
    def __init__(self, json_data):
        obj = json.loads(json_data)
        self.name = obj["name"]
        self.data = sorted(obj["data"])

    def get_duration(self):
        return max([t for (t, x) in self.data])

    def get_surrounding_points(self, runtime):
        # If runtime exceeds the total duration, return None for both points
        if runtime > self.get_duration():
            return None, None

        # Initialize variables for the previous and next points
        prev_point = None
        next_point = None

        # Iterate through the data points
        for i in range(len(self.data)):
            # Find the point where runtime falls between two data points
            if runtime < self.data[i][0]:
                prev_point = self.data[i - 1]  # The point before the runtime
                next_point = self.data[i]  # The point after the runtime
                break  # Stop the loop once the correct points are found

        # Return the previous and next points
        return prev_point, next_point

    def get_target_temperature(self, runtime):
        if runtime > self.get_duration():
            return 0

        (prev_point, next_point) = self.get_surrounding_points(runtime)

        incl = float(next_point[1] - prev_point[1]) / float(next_point[0] - prev_point[0])
        temp = prev_point[1] + (runtime - prev_point[0]) * incl
        return temp


class PID:
    def __init__(self, ki=1, kp=1, kd=1):
        # Initialize PID coefficients
        self.ki = ki  # Integral coefficient
        self.kp = kp  # Proportional coefficient
        self.kd = kd  # Derivative coefficient

        # Initialize variables for time and error tracking
        self.last_now = datetime.datetime.now()
        self.iterm = 0
        self.last_error = 0

        # Dictionary to store PID statistics
        self.pidstats = {}

    def compute(self, setpoint, current_value):
        # Compute the PID output for given setpoint and current value (current_value)

        # Calculate time elapsed since last computation
        right_now = datetime.datetime.now()
        time_delta = round((right_now - self.last_now).total_seconds())
        # Ensure time_delta is not zero to avoid division by zero
        time_delta = max(float(time_delta), 0.0001)

        # Define window size for PID control
        window_size = 100

        # Calculate error between setpoint and current value
        error = round(float(setpoint - current_value), 2)

        # Initialize variables for PID computation
        out4logs = 0
        error_derivative = 0

        # Check if error is outside the PID control window
        if error < (-1 * config.pid_control_window):
            log.info("Outside PID control window, max cooling")
            computed_output = 0
        elif error > (1 * config.pid_control_window):
            log.info("Outside PID control window, max heating")
            computed_output = 1
        else:
            # Compute integral component
            integral_component = (error * time_delta * self.ki)
            self.iterm += integral_component

            # Compute derivative component
            error_derivative = (error - self.last_error) / time_delta

            # Compute total output
            computed_output = self.kp * error + self.iterm + self.kd * error_derivative
            computed_output = sorted([-1 * window_size, computed_output, window_size])[1]  # Clamp output within window
            out4logs = computed_output
            computed_output = float(computed_output / window_size)  # Scale output

        # Update last error and time for next iteration
        self.last_error = error
        self.last_now = right_now

        # Ensure no negative output (active cooling disabled)
        if computed_output < 0:
            computed_output = 0

        # Update PID statistics
        self.pidstats = {
            'time': time.mktime(right_now.timetuple()),
            'time_delta': time_delta,
            'setpoint': setpoint,
            'current_value': current_value,
            'err': error,
            'errDelta': round(error_derivative, 3),
            'p': round(self.kp * error, 3),
            'i': round(self.iterm, 3),
            'd': round(self.kd * error_derivative, 3),
            'pid': round(out4logs, 3),
            'out': round(computed_output, 3),
        }

        # Return PID output
        return computed_output
