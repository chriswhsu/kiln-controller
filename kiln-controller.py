#!/usr/bin/env python
import os
import sys
import logging
import json
import bottle

from gevent.pywsgi import WSGIServer
from geventwebsocket.handler import WebSocketHandler
from geventwebsocket import WebSocketError

from lib.oven import SimulatedOven, RealOven, Profile
from lib.ovenWatcher import OvenWatcher

try:
    import config
except Exception as e:
    logging.error(f"Error: {e}")
    logging.error("Could not import config file.")
    logging.error("Copy config.py.EXAMPLE to config.py and adapt it for your setup.")
    exit(1)

logging.basicConfig(level=config.log_level, format=config.log_format)
log = logging.getLogger("kiln-controller")
log.info("Starting kiln controller")

script_dir = os.path.dirname(os.path.realpath(__file__))
profile_path = config.kiln_profiles_directory

app = bottle.Bottle()

if config.simulate:
    log.info("this is a simulation")
    oven = SimulatedOven()
else:
    log.info("this is a real kiln")
    oven = RealOven()

oven_watcher = OvenWatcher(oven)
# this OvenWatcher is used in the oven class for restarts
oven.set_ovenwatcher(oven_watcher)


@app.route('/')
def index():
    return bottle.redirect('/pico_reflow/index.html')


@app.get('/api/stats')
def handle_api():
    log.info("/api/stats command received")
    if hasattr(oven, 'pid'):
        if hasattr(oven.pid, 'pid_stats'):
            return json.dumps(oven.pid.pidstats)


@app.post('/api')
def handle_api():
    log.info("/api is alive")

    # run a kiln schedule
    if bottle.request.json['cmd'] == 'run':
        wanted = bottle.request.json['profile']
        log.info('api requested run of profile = %s' % wanted)

        # start at a specific minute in the schedule
        # for restarting and skipping over early parts of a schedule
        startat = 0
        if 'startat' in bottle.request.json:
            startat = bottle.request.json['startat']

        # get the wanted profile/kiln schedule
        profile = find_profile(wanted)
        if profile is None:
            return {"success": False, "error": "profile %s not found" % wanted}

        # FIXME juggling of json should happen in the Profile class
        profile_json = json.dumps(profile)
        profile = Profile(profile_json)
        oven.run_profile(profile, startat=startat)
        oven_watcher.record(profile)

    if bottle.request.json['cmd'] == 'stop':
        log.info("api stop command received")
        oven.abort_run()

    if bottle.request.json['cmd'] == 'memo':
        log.info("api memo command received")
        memo = bottle.request.json['memo']
        log.info(f"memo={memo}")

    # get stats during a run
    if bottle.request.json['cmd'] == 'stats':
        log.info("api stats command received")
        if hasattr(oven, 'pid'):
            if hasattr(oven.pid, 'pid_stats'):
                return json.dumps(oven.pid.pidstats)

    return {"success": True}


def find_profile(wanted):

    # given a wanted profile name, find it and return the parsed
    # json profile object or None.

    # load all profiles from disk
    profiles = get_profiles()
    json_profiles = json.loads(profiles)

    # find the wanted profile
    for profile in json_profiles:
        if profile['name'] == wanted:
            return profile
    return None


@app.route('/pico_reflow/:filename#.*#')
def send_static(filename):
    log.debug("serving %s" % filename)
    return bottle.static_file(filename, root=os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), "public"))


def get_websocket_from_request():
    env = bottle.request.environ
    websocket = env.get('wsgi.websocket')
    if not websocket:
        bottle.abort(400, 'Expected WebSocket request.')
    return websocket


@app.route('/control')
def handle_control():
    websocket = get_websocket_from_request()
    log.info("websocket (control) opened")
    while True:
        try:
            message = websocket.receive()
            if message:
                log.info("Received (control): %s" % message)
                msgdict = json.loads(message)
                if msgdict.get("cmd") == "RUN":
                    log.info("RUN command received")
                    profile_obj = msgdict.get('profile')
                    if profile_obj:
                        profile_json = json.dumps(profile_obj)
                        profile = Profile(profile_json)
                        oven.run_profile(profile)
                        oven_watcher.record(profile)
                    else:
                        log.error("No profile defined.  Aborting.")
                        bottle.abort()

                elif msgdict.get("cmd") == "SIMULATE":
                    log.info("SIMULATE command received")
                    # profile_obj = msgdict.get('profile')
                    # if profile_obj:
                    #    profile_json = json.dumps(profile_obj)
                    #    profile = Profile(profile_json)
                    # simulated_oven = Oven(simulate=True, time_step=0.05)
                    # simulation_watcher = OvenWatcher(simulated_oven)
                    # simulation_watcher.add_observer(websocket)
                    # simulated_oven.run_profile(profile)
                    # simulation_watcher.record(profile)
                elif msgdict.get("cmd") == "STOP":
                    log.info("Stop command received")
                    oven.abort_run()
        except WebSocketError as wse:
            log.error(wse)
            break
    log.info("websocket (control) closed")


@app.route('/storage')
def handle_storage():
    websocket = get_websocket_from_request()
    log.info("WebSocket (storage) opened")
    while True:
        try:
            message = websocket.receive()
            if not message:
                break
            log.debug("WebSocket (storage) received: %s" % message)

            if message == "GET":
                log.info("GET command received")
                websocket.send(get_profiles())
            else:
                try:
                    msgdict = json.loads(message)
                    process_storage_command(msgdict, websocket)
                except json.JSONDecodeError as error:
                    log.error(f"JSON decoding error: {error}")

        except WebSocketError:
            break
    log.info("WebSocket (storage) closed")


def process_storage_command(msgdict, websocket):
    cmd = msgdict.get("cmd")

    if cmd == "DELETE":
        handle_delete_command(msgdict, websocket)
    elif cmd == "PUT":
        handle_put_command(msgdict, websocket)


def handle_delete_command(msgdict, websocket):
    log.info("DELETE command received")
    profile_obj = msgdict.get('profile')
    response = "OK" if delete_profile(profile_obj) else "FAIL"
    msgdict["resp"] = response
    websocket.send(json.dumps(msgdict))


def handle_put_command(msgdict, websocket):
    log.info("PUT command received")
    profile_obj = msgdict.get('profile')
    force = True  # or extract from msgdict if necessary
    response = "OK" if save_profile(profile_obj, force) else "FAIL"
    msgdict["resp"] = response
    log.debug(f"WebSocket (storage) sent: {json.dumps(msgdict)}")
    websocket.send(json.dumps(msgdict))
    websocket.send(get_profiles())


@app.route('/config')
def handle_config():
    websocket = get_websocket_from_request()
    log.info("websocket (config) opened")
    try:
        websocket.send(get_config())
    except WebSocketError:
        log.error("Error with Websocket in Config")
    log.info("websocket (config) closed")


@app.route('/status')
def handle_status():
    websocket = get_websocket_from_request()
    oven_watcher.add_observer(websocket)
    log.info("websocket (status) opened")
    while True:
        try:
            message = websocket.receive()
            websocket.send("Your message was: %r" % message)
        except WebSocketError:
            break
    log.info("websocket (status) closed")


def get_profiles():
    try:
        profile_files = os.listdir(profile_path)
    except Exception as error:
        log.error(f"Error loading profile path: {error}")
        profile_files = []
    profiles = []
    for filename in profile_files:
        with open(os.path.join(profile_path, filename), 'r') as f:
            profiles.append(json.load(f))
    return json.dumps(profiles)


def save_profile(profile, force=False):
    profile_json = json.dumps(profile)
    filename = profile['name'] + ".json"
    filepath = os.path.join(profile_path, filename)
    if not force and os.path.exists(filepath):
        log.error("Could not write, %s already exists" % filepath)
        return False
    with open(filepath, 'w+') as f:
        f.write(profile_json)
        f.close()
    log.info("Wrote %s" % filepath)
    return True


def delete_profile(profile):
    filename = profile['name'] + ".json"
    filepath = os.path.join(profile_path, filename)
    os.remove(filepath)
    log.info("Deleted %s" % filepath)
    return True


def get_config():
    return json.dumps({"temp_scale": config.temp_scale,
                       "time_scale_slope": config.time_scale_slope,
                       "time_scale_profile": config.time_scale_profile,
                       "kwh_rate": config.kwh_rate,
                       "currency_type": config.currency_type})


def main():
    ip = config.ip_address
    port = config.listening_port
    log.info("listening on %s:%d" % (ip, port))

    server = WSGIServer((ip, port), app, handler_class=WebSocketHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
