import datetime
import time
import logging

import config

log = logging.getLogger(__name__)


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

        log.info(self.pidstats)

        # Return PID output
        return computed_output
