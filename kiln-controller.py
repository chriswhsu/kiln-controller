#!/usr/bin/env python
import json
import logging
import os
import sys

import bottle
from gevent.pywsgi import WSGIServer
from geventwebsocket import WebSocketError
from geventwebsocket.handler import WebSocketHandler

from lib.real_oven import RealOven
from lib.simulated_oven import SimulatedOven
from lib.oven_watcher import OvenWatcher
from lib.profile import Profile
from lib.profile_manager import ProfileManager

log = logging.getLogger(__name__)

try:
    import config
except ImportError as e:
    log.error(f"Error importing config: {e}")
    log.error("Copy config.py.EXAMPLE to config.py and adapt it for your setup.")
    sys.exit(1)


class KilnController:

    def __init__(self):

        logging.basicConfig(level=config.log_level, format=config.log_format)
        log.info("Initializing the kiln controller")
        self.prof_man = ProfileManager(config.kiln_profiles_directory)

        self.script_dir = os.path.dirname(os.path.realpath(__file__))
        self.profile_path = config.kiln_profiles_directory
        self.bottle_server = bottle.Bottle()
        self.config = config

        # Initialize with the simulated oven, need to have the oven_watcher running
        # before a run starts.
        # Swap out later when actual run starts.
        self.oven = SimulatedOven()
        self.oven_watcher = OvenWatcher(self.oven)
        self.oven_watcher.start()

        self.bottle_server.route('/')(self.index)
        self.bottle_server.route('/kiln_control/:filename#.*#')(self.send_static)
        self.bottle_server.route('/control')(self.handle_control)
        self.bottle_server.route('/storage')(self.handle_storage)
        self.bottle_server.route('/config')(self.handle_config)
        self.bottle_server.route('/status')(self.handle_status)

    @staticmethod
    def index():
        return bottle.redirect('/kiln_control/index.html')

    def send_static(self, filename):
        log.debug(f"serving {filename}")
        return bottle.static_file(filename, root=os.path.join(self.script_dir, "kiln_control"))

    @staticmethod
    def get_websocket_from_request():
        env = bottle.request.environ
        websocket = env.get('wsgi.websocket')
        if not websocket:
            bottle.abort(400, 'Expected WebSocket request.')
        return websocket

    def handle_control(self):
        websocket = self.get_websocket_from_request()
        log.debug("websocket (control) opened")
        try:
            while True:
                message = websocket.receive()
                if message:
                    log.debug("Received (control): %s" % message)
                    msgdict = json.loads(message)
                    command = msgdict.get("cmd")

                    profile_dict = msgdict.get('profile')
                    if profile_dict:
                        profile = Profile(profile_dict=profile_dict)
                    else:
                        profile = None

                    if command == "RUN":
                        log.debug("RUN command received")
                        self.initialize_and_run_oven("REAL", profile)

                    elif command == "SIMULATE":
                        log.debug("SIMULATE command received")
                        self.initialize_and_run_oven("SIMULATED", profile)

                    elif command == "STOP":
                        log.info("Stop command received")
                        if self.oven:
                            self.oven.stop()
                        else:
                            log.error("No oven initialized. Aborting.")
                            bottle.abort()

        except WebSocketError as wse:
            log.error(wse)
        finally:
            websocket.close()
            log.debug("websocket (control) closed")

    def initialize_and_run_oven(self, oven_type, profile):
        if not profile:
            log.error("No profile defined. Aborting.")
            bottle.abort()
            return

        # clean up the previous oven in case we are switching from Simulated to Real or Vice Versa
        self.oven.die()  # Signal the thread to stop
        self.oven.join()  # Wait for the thread to finish

        if oven_type == "REAL":
            log.debug("RUN command received - Initializing Real Oven")
            self.oven = RealOven()
        elif oven_type == "SIMULATED":
            log.debug("SIMULATE command received - Initializing Simulated Oven")
            self.oven = SimulatedOven()
        else:
            log.error(f"Invalid oven type: {oven_type}. Aborting.")
            bottle.abort()
            return

        log.debug(f"{oven_type} Oven created")

        self.oven_watcher.set_oven(self.oven)
        self.oven_watcher.set_profile(profile)
        self.oven.run_profile(profile)

    def handle_status(self):
        log.debug("Handle Status Initialized")
        # Implementation of status handling
        websocket = self.get_websocket_from_request()
        if self.oven_watcher:
            self.oven_watcher.add_observer(websocket)
            log.debug("OvenWatcher connected to websocket.")
        log.debug("websocket (status) opened")
        try:
            while True:
                message = websocket.receive()
                websocket.send("Your message was: %r" % message)
        except WebSocketError as error:
            log.error(f"Error with WebSocket in status: {error}")
        finally:
            websocket.close()
            log.debug("websocket (status) closed")

    def handle_storage(self):
        # Implementation of storage handling
        websocket = self.get_websocket_from_request()
        log.debug("WebSocket (storage) opened")
        try:
            while True:
                message = websocket.receive()
                if not message:
                    break
                log.debug("WebSocket (storage) received: %s" % message)

                if message == "GET":
                    log.debug("GET command received")
                    websocket.send(self.prof_man.get_profiles())
                else:
                    try:
                        msgdict = json.loads(message)
                        self.prof_man.process_storage_command(msgdict, websocket)
                    except json.JSONDecodeError as error:
                        log.error(f"JSON decoding error: {error}")

        except WebSocketError as error:
            log.error(f"Error with WebSocket in storage: {error}")
        finally:
            websocket.close()
            log.debug("WebSocket (storage) closed")

    def handle_config(self):
        websocket = self.get_websocket_from_request()
        log.debug("websocket (config) opened")
        try:
            websocket.send(self.get_config())
        except WebSocketError as error:
            log.error(f"Error with WebSocket in Config: {error}")
        finally:
            websocket.close()
            log.debug("websocket (config) closed")

    def get_config(self):
        return json.dumps({"temp_scale": self.config.temp_scale,
                           "time_scale_slope": self.config.time_scale_slope,
                           "time_scale_profile": self.config.time_scale_profile,
                           'kp': config.pid_kp,
                           'ki': config.pid_ki,
                           'kd': config.pid_kd,
                           "kwh_rate": config.kwh_rate,
                           "currency_type": config.currency_type})

    def run(self):
        ip = config.ip_address
        port = config.listening_port
        log.info(f"listening on {ip}:{port}")
        server = WSGIServer((ip, port), self.bottle_server, handler_class=WebSocketHandler)
        server.serve_forever()


if __name__ == "__main__":
    kiln_controller = KilnController()
    kiln_controller.run()
