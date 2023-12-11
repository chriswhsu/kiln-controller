import logging
from simple_pid import PID as simplePID

log = logging.getLogger(__name__)


class PID:
    def __init__(self, kp, ki, kd):

        self.pid = simplePID(kp, ki, kd, setpoint=1)
        self.pid.output_limits = (0, 1)

    def compute(self, setpoint, current_value):
        # Compute the PID output for given setpoint and current value (current_value)
        self.pid.setpoint = setpoint

        return self.pid(current_value)
