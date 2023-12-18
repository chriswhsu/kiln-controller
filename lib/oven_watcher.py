import datetime
import logging
import threading
import time

import config
from lib.profile import Profile

log = logging.getLogger(__name__)


class OvenWatcher(threading.Thread):
    def __init__(self, oven, socketio=None, profile: Profile = None):
        super().__init__()
        self.temperature_history = None
        self.started = None
        self.daemon = True
        self.oven = oven
        self.socketio = socketio  # Store the SocketIO instance
        self.active_profile = profile

    def notify_all(self, message):
        # Emit message to all connected clients
        self.socketio.emit('oven_update', message)
        log.debug(f"{self._add_id()} Sent to clients: {message}")

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

            if self.socketio:
                self.socketio.emit('oven_update', oven_status)

    def sampled_temp_history(self, max_points=500):
        # First, sort the temperature history by 'time_stamp' (timestamp)
        sorted_temperature_history = sorted(self.temperature_history, key=lambda x: x['time_stamp'])

        total_points = len(sorted_temperature_history)
        if total_points <= max_points:
            points = sorted_temperature_history
        else:
            every_nth = max(1, total_points // (max_points - 1))  # Avoid division by zero
            points = sorted_temperature_history[::every_nth]

        log.info(f"Returning {len(points)} points from the current run")
        return points

    def set_profile(self, profile: Profile):
        """Set the current profile and notify clients."""
        self.active_profile = profile
        log.info(f"Profile set to: {profile.name}")

        profile_data = self.get_profile_data()
        if self.socketio and profile_data:
            self.socketio.emit('profile_changed', profile_data)
            log.debug("Profile change notification sent to clients.")

    def get_profile_data(self):
        """Return the current profile data."""
        if self.active_profile:
            return {
                "type": "profile",
                "name": self.active_profile.name,
                "data": self.active_profile.temp_cycle_steps
            }
        return None  # Return None if there's no active profile

    def send_backlog(self):
        """Sends backlog data to requesting clients."""
        if self.socketio:
            profile_data = self.get_profile_data()
            backlog = {
                'type': "backlog",
                'profile': profile_data,
                'log': self.sampled_temp_history(),
            }
            self.socketio.emit('backlog_data', backlog)
            log.info("Backlog data sent to requesting client.")
