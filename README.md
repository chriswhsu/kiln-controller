Kiln Controller
==========

Turns a Raspberry Pi into an inexpensive, web-enabled kiln controller.

**WARNING** This project involves **high voltages** and **high currents**. 

 Do not attempt this project if you do not have prior experience working with electric circuits especially 120V / 240V circuits.
 Please make sure that anything you build conforms to local electrical codes and aligns with industry best practices.
            
**WARNING** This project involves **high temperatures**. Please do not run the kiln-controller unattended.

## Features

 * Visually design and adjust kiln schedules
 * Extended Operation Capability - run continuously for extended durations
 * Multi-Device Monitoring - check status on computers, tablets, etc.
 * Pre-Run & Real-Time Cost Estimation for Firing
 * NIST-Linearized Conversion for Precise K-Type Thermocouple Readings
 * Customizable PID Parameters for Kiln Tuning
 * Temperature Monitoring Post-Schedule Completion
 * API for Flexible Schedule Start and Stop Control
 * Compatibility with MAX31856 and MAX31855 Thermocouple Boards
 * Support for Various Thermocouple Types: K, J, N, R, S, T, E, B
 * Accurate Kiln Operation Simulation
 * Adaptive Schedule Management for Slow Heating Conditions
 * Integral Wind-Up Prevention for Off-Set Point Temperatures
 * Automatic Restart Functionality in Power Outages or Similar Events
 * Integrated Wemo Switch Control for Over-Temperature Safety


**Run Kiln Schedule**

![Image](https://github.com/jbruce12000/kiln-controller/blob/master/public/assets/images/kiln-running.png)

**Edit Kiln Schedule**

![Image](https://github.com/jbruce12000/kiln-controller/blob/master/public/assets/images/kiln-schedule.png)

## Hardware

### Parts

| Image | Hardware | Description |
| ------| -------- | ----------- |
| ![Image](https://github.com/jbruce12000/kiln-controller/blob/master/public/assets/images/rpi.png) | [Raspberry Pi](https://www.adafruit.com/category/105) | Virtually any Raspberry Pi will work since only a few GPIO pins are being used. |
| ![Image](https://github.com/jbruce12000/kiln-controller/blob/master/public/assets/images/max31855.png) | [MAX31855](https://www.adafruit.com/product/269) or [MAX31856](https://www.adafruit.com/product/3263) | Thermocouple breakout board |
| ![Image](https://github.com/jbruce12000/kiln-controller/blob/master/public/assets/images/k-type-thermocouple.png) | [K-Type Thermocouple](https://www.auberins.com/index.php?main_page=product_info&cPath=20_3&products_id=39) | Invest in a heavy duty, ceramic, k-type thermocouple designed for kilns |
| ![Image](https://github.com/jbruce12000/kiln-controller/blob/master/public/assets/images/breadboard.png) | Breadboard | breadboard, ribbon cable, connector for pi's gpio pins & connecting wires |
| ![Image](https://github.com/jbruce12000/kiln-controller/blob/master/public/assets/images/ssr.png) | Solid State Relay | Zero crossing, make sure it can handle the max current of your kiln. Even if the kiln is 220V you can buy a single [3 Phase SSR](https://www.auberins.com/index.php?main_page=product_info&cPath=2_30&products_id=331). It's like having 3 SSRs in one.  Relays this big always require a heat sink. |
| ![Image](https://github.com/jbruce12000/kiln-controller/blob/master/public/assets/images/ks-1018.png) | Electric Kiln | There are many old electric kilns on the market that don't have digital controls. You can pick one up on the used market cheaply.  This controller will work with 110V or 220V (pick a proper SSR). My kiln is a Skutt KS-1018. |

### Schematic

The pi has three gpio pins connected to the MAX31855 chip. D0 is configured as an input and CS and CLK are outputs. The signal that controls the solid state relay starts as a gpio output which drives a transistor acting as a switch in front of it. This transistor provides 5V and plenty of current to control the ssr. Since only four gpio pins are in use, any pi can be used for this project. See the [config](https://github.com/jbruce12000/kiln-controller/blob/master/config.py) file for gpio pin configuration.

My controller plugs into the wall, and the kiln plugs into the controller. 

**WARNING** This project involves high voltages and high currents. Please make sure that anything you build conforms to local electrical codes and aligns with industry best practices.

![Image](https://github.com/jbruce12000/kiln-controller/blob/master/public/assets/images/schematic.png)

*Note: I tried to power my ssr directly using a gpio pin on a RaspPi 4, and it *did* work. ymmv.

## Software 

### Raspberry PI OS

Download [Raspberry PI OS](https://www.raspberrypi.org/software/). Use Rasberry PI Imaging tool to install the OS on an SD card. Boot the OS, open a terminal and...

    $ sudo apt-get update
    $ sudo apt-get dist-upgrade
    $ sudo apt-get install python3-dev python3-virtualenv  
    $ git clone https://github.com/chriswhsu/kiln-controller
    $ cd kiln-controller
    $ virtualenv -p python3 venv
    $ source venv/bin/activate
    $ pip3 install -r requirements.txt

## Configuration

All parameters are defined in config.py, review/change to your mind's content.

You should change, test, and verify PID parameters in config.py.  Here is a [PID Tuning Guide](https://github.com/jbruce12000/kiln-controller/blob/master/docs/pid_tuning.md). There is also an [autotuner](https://github.com/jbruce12000/kiln-controller/blob/master/docs/ziegler_tuning.md). Be patient with tuning. No tuning is perfect across a wide temperature range.

You may want to change the configuration parameter **sensor_time_wait**. It's the duty cycle for the entire system. 
It's set to two seconds by default which means that a decision is made every 2s about whether to turn on relay[s] and for how long. 
If you use mechanical relays, you may want to increase this. At 2s, my SSR switches 11,000 times in 13 hours.

## Usage

### Server Startup

    $ source venv/bin/activate; ./kiln-controller.py

### Autostart Server onBoot
If you want the server to autostart on boot, run the following command:

    $ /home/pi/kiln-controller/start-on-boot

### Client Access

Click http://127.0.0.1:8081 for local development or the IP
of your PI and the port defined in config.py (default 8081).

### Simulation

Start the server and select a profile and click Simulate. Simulations run at near real time.

### Watcher

If you're busy and do not want to sit around watching the web interface for problems, 
there is a watcher.py script which you can run on any machine in your local network or even on the raspberry pi
which will watch the kiln-controller process to make sure it is running a schedule, and staying within a pre-defined temperature range. 

When things go bad, it sends messages to a slack channel you define. 
I have alerts set on my android phone for that specific slack channel. Here are detailed [instructions](https://github.com/jbruce12000/kiln-controller/blob/master/docs/watcher.md).

## License

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

## Support & Contact

Please use the issue tracker for project related issues.
If you're having trouble with hardware, I did too.  Here is a [troubleshooting guide](https://github.com/jbruce12000/kiln-controller/blob/master/docs/troubleshooting.md) I created for testing RPi gpio pins.

## Origin
This project was originally forked from https://github.com/apollo-ng/picoReflow but has diverged a large amount.
Support for active cooling or fan cooling has been removed since kilns are generally not actively cooled.
