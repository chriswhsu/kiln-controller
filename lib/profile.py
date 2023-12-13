import json
from typing import Tuple, Optional


class Profile:
    def __init__(self, json_data: str):
        obj = json.loads(json_data)
        self.name = obj["name"]
        self.data = sorted(obj["data"], key=lambda x: x[0])  # Ensuring sorting by time

    def get_duration(self) -> int:
        """Return the duration of the profile."""
        return self.data[-1][0] if self.data else 0

    def get_surrounding_points(self, runtime: int) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
        """Return the data points surrounding the given current_time."""
        if not self.data or runtime < self.data[0][0]:
            # If current_time is before the start of the data, return None or the first point
            return None, self.data[0] if self.data else None

        for i in range(1, len(self.data)):
            if runtime < self.data[i][0]:
                return self.data[i - 1], self.data[i]

        return self.data[-2], self.data[-1]

    def get_target_temperature(self, current_time: int) -> float:
        """Calculate and return the target temperature at the given current_time."""
        if current_time > self.get_duration():
            return 0

        prev_point, next_point = self.get_surrounding_points(current_time)

        if prev_point is None or next_point is None or prev_point[0] == next_point[0]:
            return 0

        slope = (float(next_point[1]) - float(prev_point[1])) / (float(next_point[0]) - float(prev_point[0]))
        temp = prev_point[1] + (current_time - prev_point[0]) * slope
        return round(temp, 2)
