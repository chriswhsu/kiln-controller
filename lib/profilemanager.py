import json
import logging
import os

log = logging.getLogger(__name__)


class ProfileManager:
    def __init__(self, profile_path):
        self.profile_path = profile_path

    def process_storage_command(self, msgdict, websocket):
        cmd = msgdict.get("cmd")

        if cmd == "DELETE":
            self.handle_delete_command(msgdict, websocket)
        elif cmd == "PUT":
            self.handle_put_command(msgdict, websocket)

    def handle_delete_command(self, msg_dict, websocket):
        log.debug("DELETE command received")
        profile_obj = msg_dict.get('profile')
        response = "OK" if self.delete_profile(profile_obj) else "FAIL"
        msg_dict["resp"] = response
        websocket.send(json.dumps(msg_dict))

    def delete_profile(self, profile):
        filename = profile['name'] + ".json"
        filepath = os.path.join(self.profile_path, filename)
        os.remove(filepath)
        log.info("Deleted %s" % filepath)
        return True

    def handle_put_command(self, msgdict, websocket):
        log.debug("PUT command received")
        profile_obj = msgdict.get('profile')
        force = True  # or extract from msg_dict if necessary
        response = "OK" if self.save_profile(profile_obj, force) else "FAIL"
        msgdict["resp"] = response
        log.debug(f"WebSocket (storage) sent: {json.dumps(msgdict)}")
        websocket.send(json.dumps(msgdict))
        websocket.send(self.get_profiles())

    def save_profile(self, profile, force=False):
        profile_json = json.dumps(profile)
        filename = profile['name'] + ".json"
        filepath = os.path.join(self.profile_path, filename)
        if not force and os.path.exists(filepath):
            log.error("Could not write, %s already exists" % filepath)
            return False
        with open(filepath, 'w+') as f:
            f.write(profile_json)
            f.close()
        log.info("Wrote %s" % filepath)
        return True

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
            log.error(f"Error loading profile path: {error}")
            profile_files = []
        profiles = []
        for filename in profile_files:
            with open(os.path.join(self.profile_path, filename), 'r') as f:
                profiles.append(json.load(f))
        return json.dumps(profiles)
