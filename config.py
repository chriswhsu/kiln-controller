import logging
import os

# uncomment this if using MAX-31856
# from lib.max31856 import MAX31856

########################################################################
#   General options

# Logging
log_level = logging.INFO
log_format = '%(asctime)s %(levelname)s %(name)s: %(message)s'

# Server
ip_address = "192.168.1.185"
listening_port = 80

########################################################################
#
#   PID parameters
#
# These parameters control kiln temperature change. These settings work
# well with the simulated oven. You must tune them to work well with 
# your specific kiln.
pid_kp = 2.0  # Proportional
pid_ki = 4 / 100  # Integral
pid_kd = 100  # Derivative

# clamp output between these values
output_limits = (0, 100)

# clamp max integral accumulation
integral_limits = (0, 75)

########################################################################
#
# duty cycle of the entire system in seconds
#
# Every N seconds a decision is made about switching the relay[s]
# on & off and for how long. The thermocouple is read
# temperature_average_samples times during and the average value is used.
sensor_time_wait = 1

########################################################################
#   Simulation parameters
sim_t_env = 70.0  # deg F
element_heat_capacity = 200.0  # J/K  heat capacity of heat element
oven_heat_capacity = 1000.0  # J/K  heat capacity of oven
oven_heating_power = 1450.0  # W    heating power of oven
thermal_res_oven_to_environ = 0.5  # K/W  thermal resistance oven -> environment
thermal_res_element_to_oven = 0.05  # K/W  thermal resistance heat element -> oven

########################################################################
# Cost Information
#
# This is used to calculate a cost estimate before a run. It's also used
# to produce the actual cost during a run. My kiln has three
# elements that when my switches are set to high, consume 9460 watts.

kwh_rate = 0.20  # cost per kilowatt-hour per currency_type to calculate cost to run job
kw_elements = 1.460  # if the kiln elements are on, the wattage in kilowatts
currency_type = "$"  # Currency Symbol to show when calculating cost to run job

########################################################################
#   Time and Temperature parameters
#
# If you change the temp_scale, all settings in this file are assumed to
# be in that scale.

temp_scale = "f"  # c = Celsius | f = Fahrenheit - Unit to display
time_scale_slope = "h"  # s = Seconds | m = Minutes | h = Hours - Slope displayed in temp_scale per time_scale_slope
time_scale_profile = "m"  # s = Seconds | m = Minutes | h = Hours - Enter and view target time in time_scale_profile

# If the current temperature is below the profile pause window,
# delay the schedule until it goes back inside. This allows for heating
# as fast as possible and not continuing until temp is reached.
kiln_must_catch_up = True
# Outside this window, N degrees below  the current target time will not elapse.
profile_pause_window = 50  # degrees

# thermocouple offset
# If you put your thermocouple in ice water and it reads 36F, you can
# set this offset to -4 to compensate.  This probably means you have a
# cheap thermocouple.  Invest in a better thermocouple.
thermocouple_offset = 0

# number of samples of temperature to average.
# If you suffer from the high temperature kiln issue and have set 
# honour_thermocouple_short_errors to False,
# you will likely need to increase this (eg I use 40)
temperature_average_samples = 40

# Thermocouple AC frequency filtering - set to True if in a 50Hz locale, else leave at False for 60Hz locale
ac_freq_50hz = False

########################################################################
#   GPIO Setup (BCM SoC Numbering Schema)
#
#   Check the RasPi docs to see where these GPIOs are
#   connected on the P1 header for your board type/rev.
#   These were tested on a Pi B Rev2 but of course you
#   can use whichever GPIO you prefer/have available.

# Outputs
gpio_heat = 23  # Switches zero-cross solid-state-relay

# Thermocouple Adapter selection:
#   max31855 - bitbang SPI interface
#   max31856 - bitbang SPI interface. must specify thermocouple_type.
max31855 = 1
max31856 = 0
# see lib/max31856.py for other thermocouple_type, only applies to max31856
# uncomment this if using MAX-31856
# thermocouple_type = MAX31856.MAX31856_S_TYPE

# Thermocouple Connection (using bitbang interfaces)
gpio_sensor_cs = 27
gpio_sensor_clock = 22
gpio_sensor_data = 17
gpio_sensor_di = 10  # only used with max31856

########################################################################
# Emergencies - or maybe not
########################################################################
# There are all kinds of emergencies that can happen including:
# - temperature is too high (emergency_shutoff_temp exceeded)
# - lost connection to thermocouple
# - unknown error with thermocouple
# - too many errors in a short period from thermocouple
# but in some cases, you might want to ignore a specific error, log it,
# and continue running your profile.
ignore_lost_connection_tc = False
ignore_unknown_tc_error = False
ignore_too_many_tc_errors = False
# some kilns/thermocouples start erroneously reporting "short" 
# errors at higher temperatures due to plasma forming in the kiln.
# Set this to True to ignore these errors and assume the temperature 
# reading was correct anyway
ignore_tc_short_errors = False

# emergency shutoff the profile if this temp is reached or exceeded.
# This just shuts off the profile. If your SSR is working, your kiln will
# naturally cool off. If your SSR has failed/shorted/closed circuit, this
# means your kiln receives full power until your house burns down.
# this should not replace you watching your kiln or use of a kiln-sitter like
# an optional wemo swtich configured below if you are using a <15 Amp kiln.
emergency_shutoff_temp = 1200  # don't go above 1200, glass never needs heating higher.

# Wemo Backup Switch Control
kill_switch_enabled = True
wemo_device_name = "Kiln"

########################################################################
# automatic restarts - if you have a power brown-out and the raspberry pi
# reboots, this restarts your kiln where it left off in the firing profile.
# This only happens if power comes back before automatic_restart_window
# is exceeded (in minutes). The kiln-controller.py process must start
# automatically on boot-up for this to work.
# DO NOT put automatic_restart_state_file anywhere in /tmp. It could be
# cleaned up (deleted) by the OS on boot.
# The state file is written to disk every sensor_time_wait seconds (2s by default)
# and is written in the same directory as config.py.
automatic_restarts = False
automatic_restart_window = 5  # max minutes since power outage
automatic_restart_state_file = os.path.abspath(os.path.join(os.path.dirname(__file__), 'state.json'))

########################################################################
# load kiln profiles from this directory
# created a repo where anyone can contribute profiles. The objective is
# to load profiles from this repository by default.
# See https://github.com/jbruce12000/kiln-profiles
kiln_profiles_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), "storage", "profiles"))
