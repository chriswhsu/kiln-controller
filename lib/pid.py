import logging
import time

import config

log = logging.getLogger(__name__)


def _clamp(value, limits):
    lower, upper = limits
    if value is None:
        return None
    elif (upper is not None) and (value > upper):
        return upper
    elif (lower is not None) and (value < lower):
        return lower
    return value


class PID:
    """A merged PID controller with logging and output normalization."""

    def __init__(
            self,
            proportional_gain=config.pid_kp,
            integral_gain=config.pid_ki,
            derivative_gain=config.pid_kd,
            setpoint=70,
            starting_output=0.0,
            time_function=time.monotonic  # Required parameter for time function
    ):
        self.time_function = time_function
        self._max_output = None
        self._min_output = None
        self.Kp, self.Ki, self.Kd = proportional_gain, integral_gain, derivative_gain
        self.setpoint = setpoint
        self.derivative_on_measurement = config.derivative_on_measurement
        self.out_limits = config.output_limits
        self.int_limits = config.integral_limits
        self._proportional = 0
        self._integral = 0
        self._derivative = 0
        self._last_time = self.get_current_time()  # Use the injected time function
        self._last_output = starting_output
        self._last_error = None
        self._last_input = None
        self._integral = _clamp(starting_output, self.int_limits)
        self.reset()

    def reset(self):
        """
        Reset the PID controller internals.

        This sets each term to 0 as well as clearing the integral, the last output and the last
        input (derivative calculation).
        """
        self._proportional = 0
        self._integral = 0
        self._derivative = 0
        self._last_time = self.get_current_time()
        self._last_output = None
        self._last_input = 0  # Initialize _last_input to 0
        self._last_error = 0  # Initialize _last_error to 0

    def get_current_time(self):
        return self.time_function()

    def compute(self, setpoint, actual_temp):

        self.setpoint = setpoint

        now = self.get_current_time()
        elapsed_time = now - self._last_time if (now - self._last_time) else 1e-16

        error = self.setpoint - actual_temp
        d_input, d_error = actual_temp - self._last_input, error - self._last_error

        self._proportional = self.Kp * error

        self._integral += self.Ki * error * elapsed_time
        self._integral = _clamp(self._integral, self.int_limits)

        if self.derivative_on_measurement:
            self._derivative = -self.Kd * d_input / elapsed_time
        else:
            self._derivative = self.Kd * d_error / elapsed_time

        output = self._proportional + self._integral + self._derivative
        output = _clamp(output, self.out_limits)

        self._last_output = output
        self._last_input = actual_temp
        self._last_error = error

        self._last_time = now  # suggestion 1: update self._last_time immediately after calculating elapsed_time

        # suggestion 2: directly use self._proportional, self._integral, and self._derivative
        log.info(f"Setpoint: {self.setpoint:.2f}, Actual: {actual_temp:.2f}, Output: {output:.2f}, P: {self._proportional:.3f}, I: {self._integral:.3f}, D: {self._derivative:.3f}")

        return output / 100
