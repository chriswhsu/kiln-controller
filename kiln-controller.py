#!/usr/bin/env python
import os
import sys
import logging
import json
import bottle
from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler
from geventwebsocket import WebSocketError

from lib.oven import SimulatedOven, RealOven
from lib.profile import Profile
from lib.ovenWatcher import OvenWatcher

try:
    import config
except ImportError as e:
    logging.error(f"Error importing config: {e}")
    logging.error("Copy config.py.EXAMPLE to config.py and adapt it for your setup.")
    sys.exit(1)


class KilnController:
    log = logging.getLogger("kiln-controller")

    def __init__(self):

        logging.basicConfig(level=config.log_level, format=config.log_format)
        self.log.info("Initializing the kiln controller")

        self.script_dir = os.path.dirname(os.path.realpath(__file__))
        self.profile_path = config.kiln_profiles_directory
        self.app = bottle.Bottle()
        self.config = config

        self.oven = SimulatedOven()
        # Initialize with the simulated oven, need to have the oven_watcher running
        # before a run starts.
        # Swap out later when actual run starts.
        self.oven_watcher = OvenWatcher(self.oven)
        self.oven.set_ovenwatcher(self.oven_watcher)

        self.app.route('/')(self.index)
        self.app.get('/api/stats')(self.handle_api_stats)
        self.app.post('/api')(self.handle_api)
        self.app.route('/kiln_control/:filename#.*#')(self.send_static)
        self.app.route('/control')(self.handle_control)
        self.app.route('/storage')(self.handle_storage)
        self.app.route('/config')(self.handle_config)
        self.app.route('/status')(self.handle_status)

    @staticmethod
    def index():
        return bottle.redirect('/kiln_control/index.html')

    def handle_api_stats(self):
        self.log.debug("/api/stats command received")
        if hasattr(self.oven, 'pid'):
            if hasattr(self.oven.pid, 'pid_stats'):
                return json.dumps(self.oven.pid.pidstats)

    def handle_api(self):
        # Implementation of API handling
        self.log.debug("/api is alive")

        # run a kiln schedule
        if bottle.request.json['cmd'] == 'run':
            selected_profile = bottle.request.json['profile']
            self.log.info('api requested run of profile = %s' % selected_profile)

            # start at a specific minute in the schedule
            # for restarting and skipping over early parts of a schedule
            startat = 0
            if 'startat' in bottle.request.json:
                startat = bottle.request.json['startat']

            # get the profile/kiln schedule
            profile = self.find_profile(selected_profile)
            if profile is None:
                return {"success": False, "error": "profile %s not found" % selected_profile}

            # FIXME juggling of json should happen in the Profile class
            profile_json = json.dumps(profile)
            profile = Profile(profile_json)
            self.oven.run_profile(profile, startat=startat)
            self.oven_watcher.record(profile)

        if bottle.request.json['cmd'] == 'stop':
            self.log.info("api stop command received")
            self.oven.abort_run()

        if bottle.request.json['cmd'] == 'memo':
            self.log.debug("api memo command received")
            memo = bottle.request.json['memo']
            self.log.debug(f"memo={memo}")

        # get stats during a run
        if bottle.request.json['cmd'] == 'stats':
            self.log.debug("api stats command received")
            if hasattr(self.oven, 'pid'):
                if hasattr(self.oven.pid, 'pid_stats'):
                    return json.dumps(self.oven.pid.pidstats)

        return {"success": True}

    def send_static(self, filename):
        self.log.debug(f"serving {filename}")
        return bottle.static_file(filename, root=os.path.join(self.script_dir, "public"))

    @staticmethod
    def get_websocket_from_request():
        env = bottle.request.environ
        websocket = env.get('wsgi.websocket')
        if not websocket:
            bottle.abort(400, 'Expected WebSocket request.')
        return websocket

    def handle_control(self):
        websocket = self.get_websocket_from_request()
        self.log.debug("websocket (control) opened")
        try:
            while True:
                message = websocket.receive()
                if message:
                    self.log.debug("Received (control): %s" % message)
                    msgdict = json.loads(message)

                    if msgdict.get("cmd") == "RUN":
                        self.log.debug("RUN command received")
                        # Reinitialize a real oven
                        self.oven = RealOven()
                        self.log.debug("Real oven created")
                        self.oven_watcher.set_oven(self.oven)  # Update the oven_watcher with the real oven
                        self.oven.set_ovenwatcher(self.oven_watcher)

                        self.process_run_command(msgdict)

                    elif msgdict.get("cmd") == "SIMULATE":
                        self.log.debug("SIMULATE command received")
                        # Reinitialize the simulated oven and set the oven_watcher
                        self.log.info("Simulated oven created")
                        self.oven = SimulatedOven()
                        self.oven_watcher.set_oven(self.oven)
                        self.oven.set_ovenwatcher(self.oven_watcher)

                        self.process_run_command(msgdict)

                    elif msgdict.get("cmd") == "STOP":
                        self.log.info("Stop command received")
                        if self.oven:
                            self.oven.stop()
                        else:
                            self.log.error("No oven initialized. Aborting.")
                            bottle.abort()

                    # Add additional command handling here if necessary

        except WebSocketError as wse:
            self.log.error(wse)
        finally:
            websocket.close()
            self.log.debug("websocket (control) closed")

    def process_run_command(self, msgdict):
        profile_obj = msgdict.get('profile')
        if profile_obj:
            profile_json = json.dumps(profile_obj)
            profile = Profile(profile_json)
            self.oven.run_profile(profile)
            self.oven_watcher.record(profile)
        else:
            self.log.error("No profile defined. Aborting.")
            bottle.abort()

    def handle_storage(self):
        # Implementation of storage handling
        websocket = self.get_websocket_from_request()
        self.log.debug("WebSocket (storage) opened")
        try:
            while True:
                message = websocket.receive()
                if not message:
                    break
                self.log.debug("WebSocket (storage) received: %s" % message)

                if message == "GET":
                    self.log.debug("GET command received")
                    websocket.send(self.get_profiles())
                else:
                    try:
                        msgdict = json.loads(message)
                        self.process_storage_command(msgdict, websocket)
                    except json.JSONDecodeError as error:
                        self.log.error(f"JSON decoding error: {error}")

        except WebSocketError as error:
            self.log.error(f"Error with WebSocket in storage: {error}")
        finally:
            websocket.close()
            self.log.debug("WebSocket (storage) closed")

    def handle_config(self):
        websocket = self.get_websocket_from_request()
        self.log.debug("websocket (config) opened")
        try:
            websocket.send(self.get_config())
        except WebSocketError as error:
            self.log.error(f"Error with WebSocket in Config: {error}")
        finally:
            websocket.close()
            self.log.debug("websocket (config) closed")

    def handle_status(self):
        self.log.debug("Handle Status Initialized")
        # Implementation of status handling
        websocket = self.get_websocket_from_request()
        if self.oven_watcher:
            self.oven_watcher.add_observer(websocket)
            self.log.debug("OvenWatcher connected to websocket.")
        self.log.debug("websocket (status) opened")
        try:
            while True:
                message = websocket.receive()
                websocket.send("Your message was: %r" % message)
        except WebSocketError as error:
            self.log.error(f"Error with WebSocket in status: {error}")
        finally:
            websocket.close()
            self.log.debug("websocket (status) closed")

    def run(self):
        ip = config.ip_address
        port = config.listening_port
        self.log.info(f"listening on {ip}:{port}")
        server = WSGIServer((ip, port), self.app, handler_class=WebSocketHandler)
        server.serve_forever()

    def find_profile(self, selected_profile):

        # given a selected_profile profile name, find it and return the parsed json profile object or None.

        profiles = self.get_profiles()
        json_profiles = json.loads(profiles)

        # find the selected_profile profile
        for profile in json_profiles:
            if profile['name'] == selected_profile:
                return profile
        return None

    def get_profiles(self):
        try:
            profile_files = os.listdir(self.profile_path)
        except Exception as error:
            self.log.error(f"Error loading profile path: {error}")
            profile_files = []
        profiles = []
        for filename in profile_files:
            with open(os.path.join(self.profile_path, filename), 'r') as f:
                profiles.append(json.load(f))
        return json.dumps(profiles)

    def process_storage_command(self, msgdict, websocket):
        cmd = msgdict.get("cmd")

        if cmd == "DELETE":
            self.handle_delete_command(msgdict, websocket)
        elif cmd == "PUT":
            self.handle_put_command(msgdict, websocket)

    def handle_delete_command(self, msgdict, websocket):
        self.log.debug("DELETE command received")
        profile_obj = msgdict.get('profile')
        response = "OK" if self.delete_profile(profile_obj) else "FAIL"
        msgdict["resp"] = response
        websocket.send(json.dumps(msgdict))

    def handle_put_command(self, msgdict, websocket):
        self.log.debug("PUT command received")
        profile_obj = msgdict.get('profile')
        force = True  # or extract from msgdict if necessary
        response = "OK" if self.save_profile(profile_obj, force) else "FAIL"
        msgdict["resp"] = response
        self.log.debug(f"WebSocket (storage) sent: {json.dumps(msgdict)}")
        websocket.send(json.dumps(msgdict))
        websocket.send(self.get_profiles())

    def save_profile(self, profile, force=False):
        profile_json = json.dumps(profile)
        filename = profile['name'] + ".json"
        filepath = os.path.join(self.profile_path, filename)
        if not force and os.path.exists(filepath):
            self.log.error("Could not write, %s already exists" % filepath)
            return False
        with open(filepath, 'w+') as f:
            f.write(profile_json)
            f.close()
        self.log.info("Wrote %s" % filepath)
        return True

    def delete_profile(self, profile):
        filename = profile['name'] + ".json"
        filepath = os.path.join(self.profile_path, filename)
        os.remove(filepath)
        self.log.info("Deleted %s" % filepath)
        return True

    def get_config(self):
        return json.dumps({"temp_scale": self.config.temp_scale,
                           "time_scale_slope": self.config.time_scale_slope,
                           "time_scale_profile": self.config.time_scale_profile,
                           'kp': config.pid_kp,
                           'ki': config.pid_ki,
                           'kd': config.pid_kd,
                           "kwh_rate": config.kwh_rate,
                           "currency_type": config.currency_type})


if __name__ == "__main__":
    kiln_controller = KilnController()
    kiln_controller.run()
