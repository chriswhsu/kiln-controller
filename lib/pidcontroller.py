import logging

from lib.simplePID import PID

log = logging.getLogger(__name__)


class PIDController:
    def __init__(self, kp, ki, kd):
        self.pid = PID(kp, ki, kd, setpoint=70, output_limits=(0, 100), integral_limits=(0, 30))

    def compute(self, setpoint, current_value):
        # Compute the PIDController output for given setpoint and current value (current_value)

        # first set the current setpoint
        self.pid.setpoint = setpoint

        output = self.pid(current_value)

        p, i, d = self.pid.components  # The separate terms are now in p, i, d
        log.info(f"Setpoint: {setpoint:.2f}, Actual: {current_value:.2f}, Output: {output:.2f}, P: {p:.3f}, I: {i:.3f}, D: {d:.3f}")

        #  return pid output value as a decimal representation of a percentence
        return output / 100
