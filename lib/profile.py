import json
from typing import Tuple, Optional


class Profile:
    def __init__(self, profile_dict: dict):
        self.name = profile_dict["name"]
        self.temp_cycle_steps = sorted(profile_dict["data"], key=lambda x: x[0])

    def get_duration(self) -> int:
        """Return the duration of the profile."""
        return self.temp_cycle_steps[-1][0] if self.temp_cycle_steps else 0

    def get_target_temperature(self, current_time: int) -> float:
        """Calculate and return the target temperature at the given current_time."""
        if current_time > self.get_duration():
            return 0

        prev_point, next_point = self._get_surrounding_points(current_time)

        if prev_point is None or next_point is None or prev_point[0] == next_point[0]:
            return 0

        slope = (float(next_point[1]) - float(prev_point[1])) / (float(next_point[0]) - float(prev_point[0]))
        temp = prev_point[1] + (current_time - prev_point[0]) * slope
        return round(temp, 2)

    def _get_surrounding_points(self, runtime: int) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
        """Return the data points surrounding the given current_time."""
        if not self.temp_cycle_steps or runtime < self.temp_cycle_steps[0][0]:
            # If current_time is before the start of the data, return None or the first point
            return None, self.temp_cycle_steps[0] if self.temp_cycle_steps else None

        for i in range(1, len(self.temp_cycle_steps)):
            if runtime < self.temp_cycle_steps[i][0]:
                return self.temp_cycle_steps[i - 1], self.temp_cycle_steps[i]

        return self.temp_cycle_steps[-2], self.temp_cycle_steps[-1]
