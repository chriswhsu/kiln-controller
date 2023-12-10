import logging
import threading
import time

import config

log = logging.getLogger(__name__)


class TempSensor(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.temperature = 0
        self.bad_percent = 0
        self.time_step = config.sensor_time_wait
        self.noConnection = self.shortToGround = self.shortToVCC = self.unknownError = False

    def run(self):
        pass


class TempSensorSimulated(TempSensor):
    # not much here, just need to be able to set the temperature

    def __init__(self):
        TempSensor.__init__(self)


class TempSensorReal(TempSensor):
    # real temperature sensor thread that takes N measurements during the time_step

    def __init__(self):
        TempSensor.__init__(self)
        self.sleep_time = self.time_step / float(config.temperature_average_samples)
        self.bad_count = 0
        self.ok_count = 0
        self.bad_stamp = 0

        if config.max31855:
            log.info("init MAX31855")
            from lib.max31855 import MAX31855
            self.thermocouple = MAX31855(config.gpio_sensor_cs,
                                         config.gpio_sensor_clock,
                                         config.gpio_sensor_data,
                                         config.temp_scale)

        if config.max31856:
            log.info("init MAX31856")
            from lib.max31856 import MAX31856
            software_spi = {'cs': config.gpio_sensor_cs,
                            'clk': config.gpio_sensor_clock,
                            'do': config.gpio_sensor_data,
                            'di': config.gpio_sensor_di}
            self.thermocouple = MAX31856(tc_type=config.thermocouple_type,
                                         software_spi=software_spi,
                                         units=config.temp_scale,
                                         ac_freq_50hz=config.ac_freq_50hz,
                                         )

    def run(self):
        # use a moving average of config.temperature_average_samples across the time_step
        temps = []
        while True:
            # reset error counter if time is up
            if (time.time() - self.bad_stamp) > (self.time_step * 2):
                if self.bad_count + self.ok_count:
                    self.bad_percent = (self.bad_count / (self.bad_count + self.ok_count)) * 100
                else:
                    self.bad_percent = 0
                self.bad_count = 0
                self.ok_count = 0
                self.bad_stamp = time.time()

            temp = self.thermocouple.get()
            self.noConnection = self.thermocouple.noConnection
            self.shortToGround = self.thermocouple.shortToGround
            self.shortToVCC = self.thermocouple.shortToVCC
            self.unknownError = self.thermocouple.unknownError

            is_bad_value = self.noConnection | self.unknownError
            if not config.ignore_tc_short_errors:
                is_bad_value |= self.shortToGround | self.shortToVCC

            if not is_bad_value:
                temps.append(temp)
                if len(temps) > config.temperature_average_samples:
                    del temps[0]
                self.ok_count += 1

            else:
                log.error("Problem reading temp N/C:%s GND:%s VCC:%s ???:%s" % (self.noConnection, self.shortToGround, self.shortToVCC, self.unknownError))
                self.bad_count += 1

            if len(temps):
                self.temperature = self.get_avg_temp(temps)
            time.sleep(self.sleep_time)

    @staticmethod
    def get_avg_temp(temps, chop=25):

        # strip off chop percent from the beginning and end of the sorted temps then return the average of what is left

        chop = chop / 100
        temps = sorted(temps)
        total = len(temps)
        items = int(total * chop)
        temps = temps[items:total - items]
        return sum(temps) / len(temps)
