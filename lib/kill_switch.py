import logging
import pywemo

log = logging.getLogger(__name__)


class KillSwitchNotFoundError(Exception):
    pass


class KillSwitch:
    def __init__(self, configuration):
        self.config = configuration
        devices = pywemo.discover_devices()
        # look for device based upon configured name, but assign none if no match.
        self.wemo_device = next((dev for dev in devices if dev.name == self.config.wemo_device_name), None)
        log.info("Kill switch initialized.")

        if self.wemo_device is None:
            log.error("Configured Kill Switch Not Found, don't continue.")
            log.error("Please check config.wemo_device_name.")
            raise KillSwitchNotFoundError("Configured Kill Switch Not Found.")

    def kill(self):
        if self.wemo_device:
            self.wemo_device.off()
        else:
            log.error("Attempted to kill, but no WeMo device is configured.")
