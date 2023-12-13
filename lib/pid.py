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
            error_map=None,
            starting_output=0.0,
    ):
        self.Kp, self.Ki, self.Kd = proportional_gain, integral_gain, derivative_gain
        self.setpoint = setpoint
        self.derivative_on_measurement = config.derivative_on_measurement
        self.error_map = error_map
        self.output_limits = config.output_limits
        self.integral_limits = config.integral_limits
        self._proportional = 0
        self._integral = 0
        self._derivative = 0
        self._last_time = None
        self._last_output = None
        self._last_error = None
        self._last_input = None
        self.time_fn = time.monotonic
        self.reset()
        self._integral = _clamp(starting_output, self.integral_limits)

    def compute(self, setpoint, actual_temp):

        self.setpoint = setpoint

        now = self.time_fn()
        elapsed_time = now - self._last_time if (now - self._last_time) else 1e-16
        error = self.setpoint - actual_temp
        d_input = actual_temp - (self._last_input if (self._last_input is not None) else actual_temp)
        d_error = error - (self._last_error if (self._last_error is not None) else error)

        if self.error_map is not None:
            error = self.error_map(error)

        self._proportional = self.Kp * error

        self._integral += self.Ki * error * elapsed_time
        self._integral = _clamp(self._integral, self.integral_limits)

        if self.derivative_on_measurement:
            self._derivative = -self.Kd * d_input / elapsed_time
        else:
            self._derivative = self.Kd * d_error / elapsed_time

        output = self._proportional + self._integral + self._derivative
        output = _clamp(output, self.output_limits)

        self._last_output = output
        self._last_input = actual_temp
        self._last_error = error
        self._last_time = now

        p, i, d = self.components
        log.info(f"Setpoint: {self.setpoint:.2f}, Actual: {actual_temp:.2f}, Output: {output:.2f}, P: {p:.3f}, I: {i:.3f}, D: {d:.3f}")

        return output / 100

    def __repr__(self):
        return (
            f'{self.__class__.__name__}('
            f'proportional_gain={self.Kp!r}, integral_gain={self.Ki!r}, derivative_gain={self.Kd!r}, '
            f'setpoint={self.setpoint!r}, '
            f'output_limits={self.output_limits!r}, '
            f'differential_on_measurement={self.derivative_on_measurement!r}, '
            f'error_map={self.error_map!r}'
            ')'
        )

    @property
    def components(self):
        """
        The P-, I- and D-terms from the last computation as separate components as a tuple. Useful
        for visualizing what the controller is doing or when tuning hard-to-tune systems.
        """
        return self._proportional, self._integral, self._derivative

    @property
    def tunings(self):
        """The tunings used by the controller as a tuple: (proportional_gain, integral_gain, derivative_gain)."""
        return self.Kp, self.Ki, self.Kd

    @tunings.setter
    def tunings(self, tunings):
        """Set the PID tunings."""
        self.Kp, self.Ki, self.Kd = tunings

    @property
    def output_limits(self):
        """
        The current output limits as a 2-tuple: (lower, upper).
        See also the *output_limits* parameter in :meth:`PID.__init__`.
        """
        return self._min_output, self._max_output

    @output_limits.setter
    def output_limits(self, limits):
        """Set the output limits."""
        if limits is None:
            self._min_output, self._max_output = None, None
            return

        min_output, max_output = limits

        if (None not in limits) and (max_output < min_output):
            raise ValueError('lower limit must be less than upper limit')

        self._min_output = min_output
        self._max_output = max_output

        self._integral = _clamp(self._integral, self.integral_limits)
        self._last_output = _clamp(self._last_output, self.output_limits)

    def reset(self):
        """
        Reset the PID controller internals.

        This sets each term to 0 as well as clearing the integral, the last output and the last
        input (derivative calculation).
        """
        self._proportional = 0
        self._integral = 0
        self._derivative = 0

        self._integral = _clamp(self._integral, self.integral_limits)

        self._last_time = self.time_fn()
        self._last_output = None
        self._last_input = None