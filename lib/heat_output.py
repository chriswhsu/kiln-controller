import logging
from gevent import sleep

log = logging.getLogger(__name__)


class HeatOutput:
    def __init__(self, configuration):
        self.config = configuration
        self.GPIO = None
        self.active = False
        self.load_libs()

    def load_libs(self):
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self.config.gpio_heat, GPIO.OUT)
            self.active = True
            self.GPIO = GPIO
        except Exception as e:
            log.warning(f"Could not initialize GPIOs, oven operation will only be simulated: {e}")
            self.active = False

    def heat(self, sleep_for):
        self.GPIO.output(self.config.gpio_heat, self.GPIO.HIGH)
        sleep(sleep_for)

    def cool(self, sleep_for):
        # no active cooling, so sleep
        self.GPIO.output(self.config.gpio_heat, self.GPIO.LOW)
        sleep(sleep_for)
