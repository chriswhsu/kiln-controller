import datetime
import logging

from gevent import Greenlet

from lib.profile import Profile

log = logging.getLogger(__name__)


class OvenWatcher(Greenlet):
    def __init__(self, oven, configuration, socketio=None, profile: Profile = None):
        super(OvenWatcher, self).__init__()
        self.config = configuration
        self.temperature_history = None
        self.start_time = None
        self.oven = oven
        self.socketio = socketio  # Store the SocketIO instance
        self.active_profile = profile
        self.greenlet = None

    def _add_id(self):
        """Helper method to standardize log messages with instance identifier."""
        instance_id = id(self)
        return f"[Instance: {instance_id}]"

    # Needed for swapping out oven after initial program initialization
    def set_oven(self, oven):
        self.oven = oven

    def reset_temp_history(self):
        self.temperature_history = []

    def _run(self):
        self.start_time = datetime.datetime.now()
        self.temperature_history = []

        while True:
            oven_status = self.oven.get_status()
            oven_state = oven_status.get("state")

            if oven_state == "RUNNING":
                self.temperature_history.append(oven_status)
                self.socketio.sleep(self.oven.time_step)
            elif oven_state == "COMPLETE":
                self.temperature_history.append(oven_status)
                self.socketio.sleep(self.config.idle_sample_time)
            elif oven_state == "IDLE":
                if len(self.temperature_history) > 0:
                    self.reset_temp_history()
                self.active_profile = None
                self.socketio.sleep(self.config.idle_sample_time)
            else:
                self.socketio.sleep(self.config.idle_sample_time)

            if self.socketio:
                log.debug("Emit oven_update")
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
            log.info(F"Backlog data sent to requesting client:{backlog}")
