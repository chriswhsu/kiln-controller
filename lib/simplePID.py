import logging
import time

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


class PID(object):
    """A simple PID controller."""

    def __init__(
            self,
            proportional_gain,
            integral_gain,
            derivative_gain,
            setpoint=0,
            output_limits=(None, None),
            integral_limits=(None, None),
            proportional_on_measurement=False,
            differential_on_measurement=True,
            error_map=None,
            starting_output=0.0,
    ):
        """
        Initialize a new PID controller.

        :param proportional_gain: The value for the proportional gain Kp
        :param integral_gain: The value for the integral gain Ki
        :param derivative_gain: The value for the derivative gain Kd
        :param setpoint: The initial setpoint that the PID will try to achieve
        :param output_limits: The initial output limits to use, given as an iterable with 2
            elements, for example: (lower, upper). The output will never go below the lower limit
            or above the upper limit. Either of the limits can also be set to None to have no limit
            in that direction. Setting output limits also avoids integral windup, since the
            integral term will never be allowed to grow outside of the limits.
        :param proportional_on_measurement: Whether the proportional term should be calculated on
            the input directly rather than on the error (which is the traditional way). Using
            proportional-on-measurement avoids overshoot for some types of systems.
        :param differential_on_measurement: Whether the differential term should be calculated on
            the input directly rather than on the error (which is the traditional way).
        :param error_map: Function to transform the error value in another constrained value.
        :param starting_output: The starting point for the PID's output. If you start controlling
            a system that is already at the setpoint, you can set this to your best guess at what
            output the PID should give when first calling it to avoid the PID outputting zero and
            moving the system away from the setpoint.
        """
        self.Kp, self.Ki, self.Kd = proportional_gain, integral_gain, derivative_gain
        self.setpoint = setpoint

        self._min_output, self._max_output = None, None
        self.proportional_on_measurement = proportional_on_measurement
        self.differential_on_measurement = differential_on_measurement
        self.error_map = error_map

        self._proportional = 0
        self._integral = 0
        self._derivative = 0

        self._last_time = None
        self._last_output = None
        self._last_error = None
        self._last_input = None

        # Get monotonic time to ensure that time deltas are always positive
        self.time_fn = time.monotonic

        self.o_limits = output_limits
        self.i_limits = integral_limits
        self.reset()

        # Set initial state of the controller
        self._integral = _clamp(starting_output, integral_limits)

    def __call__(self, actual_temp):
        """
        Update the PID controller.

        Call the PID controller with *actual_temp* and calculate and return a control output if
        sample_time seconds has passed since the last update. If no new output is calculated,
        return the previous output instead (or None if no value has been calculated yet).

        """

        now = self.time_fn()
        elapsed_time = now - self._last_time if (now - self._last_time) else 1e-16

        # Compute error terms
        error = self.setpoint - actual_temp
        d_input = actual_temp - (self._last_input if (self._last_input is not None) else actual_temp)
        d_error = error - (self._last_error if (self._last_error is not None) else error)

        # Check if must map the error
        if self.error_map is not None:
            error = self.error_map(error)

        # Compute the proportional term
        if not self.proportional_on_measurement:
            # Regular proportional-on-error, simply set the proportional term
            self._proportional = self.Kp * error
        else:
            # Add the proportional error on measurement to error_sum
            self._proportional -= self.Kp * d_input

        # Compute integral and derivative terms
        self._integral += self.Ki * error * elapsed_time
        self._integral = _clamp(self._integral, self.i_limits)  # Avoid integral windup

        if self.differential_on_measurement:
            self._derivative = -self.Kd * d_input / elapsed_time
        else:
            self._derivative = self.Kd * d_error / elapsed_time

        # Compute final output
        output = self._proportional + self._integral + self._derivative
        output = _clamp(output, self.o_limits)

        # Keep track of state
        self._last_output = output
        self._last_input = actual_temp
        self._last_error = error
        self._last_time = now

        return output

    def __repr__(self):
        return (
            '{self.__class__.__name__}('
            'proportional_gain={self.proportional_gain!r}, integral_gain={self.integral_gain!r}, derivative_gain={self.derivative_gain!r}, '
            'setpoint={self.setpoint!r}, '
            'output_limits={self.output_limits!r}, '
            'proportional_on_measurement={self.proportional_on_measurement!r}, '
            'differential_on_measurement={self.differential_on_measurement!r}, '
            'error_map={self.error_map!r}'
            ')'
        ).format(self=self)

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

        self._integral = _clamp(self._integral, self.i_limits)
        self._last_output = _clamp(self._last_output, self.o_limits)

    def reset(self):
        """
        Reset the PID controller internals.

        This sets each term to 0 as well as clearing the integral, the last output and the last
        input (derivative calculation).
        """
        self._proportional = 0
        self._integral = 0
        self._derivative = 0

        self._integral = _clamp(self._integral, self.i_limits)

        self._last_time = self.time_fn()
        self._last_output = None
        self._last_input = None
