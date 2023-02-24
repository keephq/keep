import json
import os
from typing import Self


class StateManager:
    STATE_FILE = "keepstate.json"
    __instance = None

    # https://stackoverflow.com/questions/36286894/name-not-defined-in-type-annotation
    @staticmethod
    def get_instance() -> "StateManager":
        if StateManager.__instance == None:
            StateManager()
        return StateManager.__instance

    def __init__(self):
        if StateManager.__instance != None:
            raise Exception(
                "Singleton class is a singleton class and cannot be instantiated more than once."
            )
        else:
            StateManager.__instance = self
        self.state_file = self.STATE_FILE or os.environ.get("KEEP_STATE_FILE")

    def get_last_alert_run(self, alert_id):
        # TODO - SQLite
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
        except:
            state = {}

        if alert_id in state:
            return state[alert_id][-1]
        # no previous runs
        else:
            return {}

    def set_last_alert_run(self, alert_id, alert_context, alert_status):
        # TODO - SQLite
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
        except:
            state = {alert_id: []}
        state[alert_id].append(
            {
                "alert_status": alert_status,
                "alert_context": alert_context,
            }
        )
        with open(self.state_file, "w") as f:
            json.dump(state, f)
