import json


class Profile:
    def __init__(self, json_data):
        obj = json.loads(json_data)
        self.name = obj["name"]
        self.data = sorted(obj["data"])

    def get_duration(self):
        return max([t for (t, x) in self.data])

    def get_surrounding_points(self, runtime):
        # If runtime exceeds the total duration, return None for both points
        if runtime > self.get_duration():
            return None, None

        # Initialize variables for the previous and next points
        prev_point = None
        next_point = None

        # Iterate through the data points
        for i in range(len(self.data)):
            # Find the point where runtime falls between two data points
            if runtime < self.data[i][0]:
                prev_point = self.data[i - 1]  # The point before the runtime
                next_point = self.data[i]  # The point after the runtime
                break  # Stop the loop once the correct points are found

        # Return the previous and next points
        return prev_point, next_point

    def get_target_temperature(self, runtime):
        if runtime > self.get_duration():
            return 0

        (prev_point, next_point) = self.get_surrounding_points(runtime)

        incl = float(next_point[1] - prev_point[1]) / float(next_point[0] - prev_point[0])
        temp = prev_point[1] + (runtime - prev_point[0]) * incl
        return temp
