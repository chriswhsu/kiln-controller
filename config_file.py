import logging
import os

import local_config

# uncomment this if using MAX-31856
# from lib.max31856 import MAX31856

########################################################################
#   General options

# Logging
log_level = logging.INFO
log_format = '%(asctime)s %(levelname)s %(name)s: %(message)s'

# Server
ip_address = local_config.ip_address
listening_port = local_config.listening_port

########################################################################
#
#   PID parameters
#
# These parameters control kiln temperature change. These settings work
# well with the simulated oven. You must tune them to work well with 
# your specific kiln.
pid_kp = 1.0  # Proportional
pid_ki = 2 / 100  # Integral
pid_kd = 30  # Derivative

# Take derivative on measurement as opposed to error.
derivative_on_measurement = True

# clamp output between these values
output_limits = (0, 100)

# clamp max integral accumulation
integral_limits = (0, 100)

########################################################################
#
# duty cycle of the entire system in seconds
#
# Every N seconds a decision is made about switching the relay[s]
# on & off and for how long. The thermocouple is read
# temperature_average_samples times during and the average value is used.
sensor_time_wait = 1

# update temperature at this interval when not actively running a profile.
idle_sample_time = 2

# abort if we've applied heat and temperature is 50 deg below setpoint for this many minutes.
abort_threshold_minutes = 1
# abort if heating for more than the above number of minutes and temp is off by this much or more.
abort_temp_diff_threshold = 50
# unless the temperature is rising by at least this much per cycle.
temp_increase_threshold = 0.3

########################################################################
#   Simulation parameters
simulated_room_temp = 60.0  # deg F
element_heat_capacity = 200.0  # J/K  heat capacity of heat element
oven_heat_capacity = 1000.0  # J/K  heat capacity of oven
oven_heating_power = 1450.0  # W    heating power of oven
thermal_res_oven_to_environ = 1.2  # K/W  thermal resistance oven -> environment
thermal_res_element_to_oven = 0.08  # K/W  thermal resistance heat element -> oven

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
time_scale_profile = "h"  # s = Seconds | m = Minutes | h = Hours - Enter and view target time in time_scale_profile

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

# Thermocouple Connection (using bitbang interfaces)
gpio_sensor_cs = 27
gpio_sensor_clock = 22
gpio_sensor_data = 17

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
# this should not replace you watching your kiln.

emergency_shutoff_temp = 1200  # don't go above 1200, glass never needs heating higher.

########################################################################
# load kiln profiles from this directory
# created a repo where anyone can contribute profiles. The objective is
# to load profiles from this repository by default.
# See https://github.com/jbruce12000/kiln-profiles
kiln_profiles_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), "storage", "profiles"))


