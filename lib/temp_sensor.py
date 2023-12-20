import collections
import logging
import time
from gevent import sleep, Greenlet

log = logging.getLogger(__name__)

try:
    from lib.max31855 import MAX31855
except ImportError as e:
    log.warning(f"Could not import MAX31855: {e}")
    MAX31855 = None  # Placeholder for the MAX31855 class


class TempSensor(Greenlet):
    def __init__(self, configuration):
        super(TempSensor, self).__init__()
        self.config = configuration
        self.daemon = True
        self.temperature = 0
        self.time_step = self.config.sensor_time_wait
        self.noConnection = self.shortToGround = self.shortToVCC = self.unknownError = False


class TempSensorSimulated(TempSensor):
    # not much here, just need to be able to set the temperature

    def __init__(self, configuration):
        super().__init__(configuration)


class TempSensorReal(TempSensor):
    def __init__(self, configuration):
        super().__init__(configuration)
        self.sample_interval_seconds = 0.25  # Gather samples 4 times per second
        self.update_interval_seconds = 1  # Update temperature every 1 second
        self.sliding_window_seconds = 3
        # The deque length is based on how many samples are in the 3 second window
        self.temps = collections.deque(maxlen=int(self.sliding_window_seconds / self.sample_interval_seconds))
        self.last_update_time = time.monotonic()

        log.info("Initializing MAX31855")
        self.thermocouple = MAX31855(self.config.gpio_sensor_cs,
                                     self.config.gpio_sensor_clock,
                                     self.config.gpio_sensor_data,
                                     self.config.temp_scale)

    def _run(self):
        while True:
            current_time = time.monotonic()

            if current_time - self.last_update_time >= self.update_interval_seconds:
                if self.temps:  # Ensure there are readings to calculate average
                    self.temperature = self.get_avg_temp(list(self.temps))
                self.last_update_time = current_time

            temp, is_bad_value = self.read_temperature()

            if not is_bad_value:
                self.temps.append(temp)
            else:
                self.process_bad_temp()

            sleep(self.sample_interval_seconds)

    def read_temperature(self):
        temp = self.thermocouple.get()
        log.debug(f"Temp: {temp}")

        is_bad_value = self.thermocouple.noConnection or self.thermocouple.unknownError
        if not self.config.ignore_tc_short_errors:
            is_bad_value |= self.thermocouple.shortToGround or self.thermocouple.shortToVCC

        return temp, is_bad_value

    def process_bad_temp(self):
        log.error(
                f"Problem reading temp N/C:{self.thermocouple.noConnection} GND:{self.thermocouple.shortToGround} VCC:{self.thermocouple.shortToVCC} ???:"
                f"{self.thermocouple.unknownError}")

    @staticmethod
    def get_avg_temp(temps, chop=20):
        log.debug(f"Temps: {temps}")
        if not temps:
            return 0

        chop_percentage = chop / 100
        temps = sorted(temps)
        chop_count = int(len(temps) * chop_percentage)
        temps = temps[chop_count:-chop_count]
        return round(sum(temps) / len(temps), 2) if temps else 0
