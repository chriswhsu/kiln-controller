import json
import logging
import os
import sys

from flask import Flask, abort, redirect, send_from_directory
from flask_socketio import SocketIO, emit

from lib.oven_watcher import OvenWatcher
from lib.profile import Profile
from lib.profile_manager import ProfileManager
from lib.real_oven import RealOven
from lib.simulated_oven import SimulatedOven

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

        self.flask_app = Flask(__name__)
        self.socketio = SocketIO(self.flask_app, cors_allowed_origins="*", logger=False, engineio_logger=False)

        # Initialize with the simulated oven
        self.oven = SimulatedOven()

        # Create OvenWatcher instance with oven and socketio
        self.oven_watcher = OvenWatcher(self.oven, self.socketio)
        self.oven_watcher.start()

        @self.flask_app.route('/')
        def index():
            return redirect('/kiln_control/index.html')

        @self.flask_app.route('/kiln_control/<path:filename>')
        def send_static(filename):
            log.debug(f"serving {filename}")
            return send_from_directory(os.path.join(self.script_dir, "kiln_control"), filename)

        @self.socketio.on('request_backlog')
        def handle_request_backlog():
            # Assuming 'oven_watcher' is an instance of OvenWatcher
            self.oven_watcher.send_backlog()  # Or modify to send to specific client

        @self.socketio.on('request_profiles')
        def handle_request_profiles():
            log.info('request_profiles.')
            # Assuming 'oven_watcher' is an instance of OvenWatcher
            emit('storage_response', self.prof_man.get_profiles())

        @self.socketio.on('control')
        def handle_control(json_data):
            log.debug("WebSocket (control) received: %s" % json_data)
            try:
                # Parse the received data
                msgdict = json.loads(json_data)
                command = msgdict.get("cmd")

                profile_dict = msgdict.get('profile')
                if profile_dict:
                    profile = Profile(profile_dict=profile_dict)
                else:
                    profile = None

                # Handle different commands
                if command == "RUN":
                    log.debug("RUN command received")
                    self.initialize_and_run_oven("REAL", profile)

                elif command == "SIMULATE":
                    log.debug("SIMULATE command received")
                    self.initialize_and_run_oven("SIMULATED", profile)

                elif command == "STOP":
                    log.info("Stop command received")
                    if self.oven:
                        log.info("Oven Exists")
                        self.oven.stop()
                    else:
                        log.error("No oven initialized.")
                        emit('error', {'message': 'No oven initialized'})

            except json.JSONDecodeError as error:
                log.error(f"JSON decoding error: {error}")
                emit('error', {'message': 'JSON decoding error'})

        @self.socketio.on('storage')
        def handle_storage(data):
            # 'data' contains the message sent from the client
            log.debug("WebSocket (storage) received: %s" % data)

            if data == "GET":
                log.debug("GET command received")
                # Use emit to send data back to the client
            else:
                try:
                    msgdict = json.loads(data)
                    # Process the storage command and send response back
                    response = self.prof_man.process_storage_command(msgdict)
                    emit('storage_response', response)
                except json.JSONDecodeError as error:
                    log.error(f"JSON decoding error: {error}")
                    emit('error', {'message': 'JSON decoding error'})

        @self.socketio.on('request_config')
        def handle_config():
            log.info("handle_config")
            # Send config data
            emit('config', self.get_config())

    def initialize_and_run_oven(self, oven_type, profile):
        if not profile:
            log.error("No profile defined. Aborting.")
            abort(400, 'Expected WebSocket request.')

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
            abort(400, 'Expected WebSocket request.')

        log.debug(f"{oven_type} Oven created")

        self.oven_watcher.set_oven(self.oven)
        self.oven_watcher.set_profile(profile)

        self.oven.run_profile(profile)

    def get_config(self):
        return json.dumps({"temp_scale": config.temp_scale,
                           "time_scale_slope": config.time_scale_slope,
                           "time_scale_profile": config.time_scale_profile,
                           'kp': config.pid_kp,
                           'ki': config.pid_ki,
                           'kd': config.pid_kd,
                           "kwh_rate": config.kwh_rate,
                           "currency_type": config.currency_type})

    def run(self):
        ip = config.ip_address
        port = config.listening_port
        log.info(f"Listening on {ip}:{port}")
        # Run the Flask app with the integrated SocketIO server
        self.socketio.run(self.flask_app, host=ip, port=port)


if __name__ == "__main__":
    kiln_controller = KilnController()
    kiln_controller.run()
