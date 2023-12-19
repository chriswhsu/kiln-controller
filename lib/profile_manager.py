import json
import logging
import os

log = logging.getLogger(__name__)


class ProfileManager:
    def __init__(self, profile_path):
        self.profile_path = profile_path

    def handle_delete_command(self, msg_dict):
        log.debug("DELETE command received")
        profile_obj = msg_dict.get('profile')
        response = "OK" if self.delete_profile(profile_obj) else "FAIL"
        msg_dict["resp"] = response
        # TODO Emit response.

    def delete_profile(self, profile):
        filename = profile['name'] + ".json"
        filepath = os.path.join(self.profile_path, filename)
        os.remove(filepath)
        log.info("Deleted %s" % filepath)
        return True

    def save_profile(self, msgdict):
        profile_obj = msgdict.get('profile')
        profile_json = json.dumps(profile_obj)
        filename = profile_obj['name'] + ".json"
        filepath = os.path.join(self.profile_path, filename)

        try:
            with open(filepath, 'w+') as f:
                f.write(profile_json)
            log.info(f"Profile '{profile_obj['name']}' saved successfully.")
            return True
        except Exception as e:
            log.error(f"Error saving profile '{profile_obj['name']}': {e}")
            return False

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
        log.info(f"profiles:{profiles}")
        return json.dumps(profiles)
