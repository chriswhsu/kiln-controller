import datetime
import json
import logging
import threading
import time

from lib.profile import Profile

log = logging.getLogger(__name__)


class OvenWatcher(threading.Thread):
    def __init__(self, oven):
        super().__init__()
        self.daemon = True
        self.oven = oven
        self.last_profile = None
        self.temperature_history = []
        self.started = None
        self.observers = []

    # Needed for swapping out oven after initial program initialization
    def set_oven(self, oven):
        self.oven = oven

    def run(self):
        self.started = datetime.datetime.now()
        self.temperature_history = []

        while True:
            oven_state = self.oven.get_state()

            if oven_state.get("state") == "RUNNING":
                self.temperature_history.append(oven_state)
            self.notify_all(oven_state)
            time.sleep(self.oven.time_step)

    def sampled_temp_history(self, max_points=100):
        total_points = len(self.temperature_history)
        if total_points <= max_points:
            points = self.temperature_history
        else:
            every_nth = max(1, total_points // (max_points - 1))  # Avoid division by zero
            points = self.temperature_history[::every_nth]

        log.info(f"Returning {len(points)} points from the current run")
        return points

    def set_profile(self, profile: Profile):
        self.last_profile = profile

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
        if self.last_profile:
            return {
                "name": self.last_profile.name,
                "data": self.last_profile.temp_cycle_steps,
                "type": "profile"
            }
        return None

    def notify_all(self, message):
        message_json = json.dumps(message)
        log.debug("Sending to %d clients: %s" % (len(self.observers), message_json))
        for wsock in self.observers:
            if wsock:
                try:
                    wsock.send(message_json)
                except Exception as e:
                    log.error(f"Could not write to socket {wsock}: {e}")
                    self.observers.remove(wsock)
            else:
                self.observers.remove(wsock)
