import logging

import simple_pid

log = logging.getLogger(__name__)


class PID:
    def __init__(self, kp, ki, kd):
        self.pid = simple_pid.PID(kp, ki, kd, setpoint=1)
        self.pid.output_limits = (0, 1)

    def compute(self, setpoint, current_value):
        # Compute the PID output for given setpoint and current value (current_value)

        # first set the current setpoint
        self.pid.setpoint = setpoint

        output = self.pid(current_value)

        p, i, d = self.pid.components  # The separate terms are now in p, i, d
        log.info(f"Setpoint: {setpoint:.2f}, Actual: {current_value:.2f}, Output: {output:.2f}, P: {p:.3f}, I: {i:.3f}, D: {d:.3f}")

        # then derive and return pid output value
        return output
