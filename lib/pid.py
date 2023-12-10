import logging
from simple_pid import PID as simplePID

import config

log = logging.getLogger(__name__)


class PID:
    def __init__(self, ki=1, kp=1, kd=1):

        self.pid = simplePID(1, 0.1, 0.05, setpoint=1)
        self.pid.output_limits = (0, 1)

    def compute(self, setpoint, current_value):
        # Compute the PID output for given setpoint and current value (current_value)
        self.pid.setpoint = setpoint

        return self.pid(current_value)
