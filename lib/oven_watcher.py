import datetime
import json
import logging
import threading
import time

import config
from lib.profile import Profile

log = logging.getLogger(__name__)


class OvenWatcher(threading.Thread):
    def __init__(self, oven, profile: Profile = None):
        super().__init__()
        self.daemon = True
        self.oven = oven
        self.active_profile = profile
        self.temperature_history = []
        self.started = None
        self.observers = []

    def _add_id(self):
        """Helper method to standardize log messages with instance identifier."""
        instance_id = id(self)
        return f"[Instance: {instance_id}]"

    # Needed for swapping out oven after initial program initialization
    def set_oven(self, oven):
        self.oven = oven

    def reset_temp_history(self):
        self.temperature_history = []

    def run(self):
        self.started = datetime.datetime.now()
        self.temperature_history = []

        while True:
            oven_status = self.oven.get_status()
            oven_state = oven_status.get("state")

            if oven_state == "RUNNING":
                self.temperature_history.append(oven_status)
                time.sleep(self.oven.time_step)
            elif oven_state == "COMPLETE":
                self.temperature_history.append(oven_status)
                time.sleep(config.idle_sample_time)
            elif oven_state == "IDLE":
                if len(self.temperature_history) > 0:
                    self.reset_temp_history()
                time.sleep(config.idle_sample_time)
            else:
                time.sleep(config.idle_sample_time)
            self.notify_all(oven_status)

    def sampled_temp_history(self, max_points=500):
        # First, sort the temperature history by 'runtime' (timestamp)
        sorted_temperature_history = sorted(self.temperature_history, key=lambda x: x['runtime'])

        total_points = len(sorted_temperature_history)
        if total_points <= max_points:
            points = sorted_temperature_history
        else:
            every_nth = max(1, total_points // (max_points - 1))  # Avoid division by zero
            points = sorted_temperature_history[::every_nth]

        log.info(f"{self._add_id()} Returning {len(points)} points from the current run")
        return points

    def set_profile(self, profile: Profile):
        self.active_profile = profile

    def add_observer(self, observer):
        profile_data = self.get_profile_data()
        backlog = {
            'type': "backlog",
            'profile': profile_data,
            'log': self.sampled_temp_history(),
        }
        backlog_json = json.dumps(backlog)
        try:
            log.debug(backlog_json)
            observer.send(backlog_json)
        except Exception as e:
            log.error(f"An error occurred: {e}")
            log.error("Could not send backlog to a new observer")

        self.observers.append(observer)

    def get_profile_data(self):
        if self.active_profile:
            return {
                "name": self.active_profile.name,
                "data": self.active_profile.temp_cycle_steps,
                "type": "profile"
            }
        return None

    def notify_all(self, message):
        message_json = json.dumps(message)
        log.info(f"{self._add_id()}Sending to {len(self.observers)} clients: {message_json}")
        for wsock in self.observers:
            if wsock:
                try:
                    wsock.send(message_json)
                except Exception as e:
                    log.error(f"{self._add_id()}Could not write to socket {wsock}: {e}")
                    self.observers.remove(wsock)
            else:
                self.observers.remove(wsock)
