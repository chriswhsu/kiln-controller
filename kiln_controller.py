import json
import logging
import os

from flask import Flask, abort, redirect, send_from_directory
from flask_socketio import SocketIO, emit

import config_file
from lib.oven_factory import OvenFactory
from lib.oven_watcher import OvenWatcher
from lib.profile import Profile
from lib.profile_manager import ProfileManager

log = logging.getLogger(__name__)


class KilnController:

    def __init__(self, configuration):

        logging.basicConfig(level=configuration.log_level, format=configuration.log_format)
        self.config = configuration
        log.info("Initializing the kiln controller")
        self.prof_man = ProfileManager(self.config.kiln_profiles_directory)

        self.script_dir = os.path.dirname(os.path.realpath(__file__))
        self.profile_path = self.config.kiln_profiles_directory

        self.flask_app = Flask(__name__)
        self.socketio = SocketIO(self.flask_app, cors_allowed_origins="*", logger=False, engineio_logger=False)

        # Initialize with the simulated oven
        self.oven = OvenFactory.create_oven(OvenFactory.SIMULATED, self.config)

        # Create OvenWatcher instance with oven and socketio
        self.oven_watcher = OvenWatcher(self.oven, self.config, self.socketio)
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
            self.oven_watcher.send_backlog()  # Or modify to send to specific client

        @self.socketio.on('request_profiles')
        def handle_request_profiles():
            log.info('request_profiles.')
            emit('profile_list', self.prof_man.get_profiles())

        @self.socketio.on('control')
        def handle_control(json_data):
            log.debug("WebSocket (control) received: %s" % json_data)
            try:
                # Parse the received data
                command = json_data.get("cmd")

                profile_dict = json_data.get('profile')
                if profile_dict:
                    profile = Profile(profile_dict=profile_dict)
                else:
                    profile = None

                # Handle different commands
                if command == "RUN":
                    log.debug("RUN command received")
                    self.initialize_and_run_oven(OvenFactory.REAL, profile)

                elif command == "SIMULATE":
                    log.debug("SIMULATE command received")
                    self.initialize_and_run_oven(OvenFactory.SIMULATED, profile)

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

        @self.socketio.on('save_profile')
        def _save_profile(msgdict):
            log.debug(f"Profile to be saved received: {msgdict}")
            try:
                # Process the storage command and send response back
                success = self.prof_man.save_profile(msgdict)
                if success:
                    response = {'status': 'success', 'message': 'Profile saved successfully'}
                    emit('profile_list', self.prof_man.get_profiles())
                else:
                    response = {'status': 'failure', 'message': 'Failed to save profile'}
                emit('server_response', response)
            except Exception as error:
                log.error(f"Error processing profile save: {error}")
                emit('error', {'message': 'Error processing profile save'})

        @self.socketio.on('delete_profile')
        def _delete_profile(profile_name):
            log.info(f"Profile to be deleted: {profile_name}")
            try:
                # Process the storage command and send response back
                success = self.prof_man.delete_profile(profile_name)
                if success:
                    response = {'status': 'success', 'message': 'Profile deleted.'}
                    emit('profile_list', self.prof_man.get_profiles())
                else:
                    response = {'status': 'failure', 'message': 'Failed to delete profile'}
                emit('server_response', response)
            except Exception as error:
                log.error(f"Error processing profile delete: {error}")
                emit('error', {'message': 'Error processing profile delete'})

        @self.socketio.on('request_config')
        def _handle_config():
            log.info("handle_config")
            # Send config data
            emit('get_config', self.get_config())

    def initialize_and_run_oven(self, oven_type, profile):
        log.info(f"Initializing and running oven. Oven type: {oven_type}, Profile: {profile}")

        if not profile:
            log.error("No profile defined. Aborting.")
            abort(400, 'Expected WebSocket request.')

        log.info("Cleaning up previous oven state.")
        self.oven.die()  # Signal the thread to stop
        self.oven.join()  # Wait for the thread to finish

        try:
            log.info(f"Creating oven of type: {oven_type}")
            self.oven = OvenFactory.create_oven(oven_type, self.config)  # Using a factory to create an oven instance
            log.debug(f"Oven of type {oven_type} created successfully.")
        except Exception as e:
            log.error(f"Error while creating oven: {str(e)}")
            abort(400, 'Expected WebSocket request.')

        log.info(f"Setting oven watcher with oven: {self.oven} and profile: {profile}")
        self.oven_watcher.set_oven(self.oven)
        self.oven_watcher.set_profile(profile)

        log.info(f"Running oven profile: {profile}")
        self.oven.run_profile(profile)

    def get_config(self):
        return {"temp_scale": self.config.temp_scale,
                "time_scale_slope": self.config.time_scale_slope,
                "time_scale_profile": self.config.time_scale_profile,
                'kp': self.config.pid_kp,
                'ki': self.config.pid_ki,
                'kd': self.config.pid_kd,
                "kwh_rate": self.config.kwh_rate,
                "currency_type": self.config.currency_type}

    def run(self):
        ip = self.config.ip_address
        port = self.config.listening_port
        log.info(f"Listening on {ip}:{port}")
        # Run the Flask app with the integrated SocketIO server
        self.socketio.run(self.flask_app, host=ip, port=port, log_output=True, use_reloader=False)


if __name__ == "__main__":
    kiln_controller = KilnController(configuration=config_file)
    kiln_controller.run()
