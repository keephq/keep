import logging
import os
import time
import typing

from keep.alert.alert import Alert
from keep.parser.parser import Parser


class AlertManager:
    def __init__(self):
        self.parser = Parser()
        self.logger = logging.getLogger(__name__)

    def run(
        self,
        alerts_path: str | list[str],
        providers_file: str = None,
        interval: int = 0,
    ):
        """
        Run alerts from a file or directory.

        Args:
            alert (str): Either a an alert yaml or a directory containing alert yamls or a list of urls to get the alerts from.
            providers_file (str, optional): The path to the providers yaml. Defaults to None.
        """
        self.logger.info(
            f"Running alert(s) from {alerts_path}", extra={"interval": interval}
        )
        # If interval is set, run the alert every INTERVAL seconds until the user stops the process
        if interval > 0:
            self.logger.info(
                "Running in interval mode. Press Ctrl+C to stop the process."
            )
            while True:
                self._run(alerts_path, providers_file)
                self.logger.info(f"Sleeping for {interval} seconds...")
                time.sleep(interval)
        # If interval is not set, run the alert once
        else:
            self._run(alerts_path, providers_file)
        self.logger.info(
            f"Alert(s) from {alerts_path} ran successfully",
            extra={"interval": interval},
        )

    def _run(self, alert_path: str | list[str], providers_file: str = None):
        if isinstance(alert_path, tuple):
            for alert_url in alert_path:
                alerts = self.parser.parse(alert_url, providers_file)
                self._run_alerts(alerts)
        elif os.path.isdir(alert_path):
            self.run_from_directory(alert_path, providers_file)
        else:
            alerts = self.parser.parse(alert_path, providers_file)
            self._run_alerts(alerts)

    def run_from_directory(self, alerts_dir: str, providers_file: str = None):
        """
        Run alerts from a directory.

        Args:
            alerts_dir (str): A directory containing alert yamls.
            providers_file (str, optional): The path to the providers yaml. Defaults to None.
        """
        for file in os.listdir(alerts_dir):
            if file.endswith(".yaml") or file.endswith(".yml"):
                self.logger.info(f"Running alert from {file}")
                try:
                    alerts = self.parser.parse(
                        os.path.join(alert, file), providers_file
                    )
                    self._run_alerts(alerts)
                    self.logger.info(f"Alert from {file} ran successfully")
                except Exception as e:
                    self.logger.error(
                        f"Error running alert from {file}", extra={"exception": e}
                    )

    def _run_alerts(self, alerts: typing.List[Alert]):
        for alert in alerts:
            self.logger.info(f"Running alert {alert.alert_id}")
            try:
                alert.run()
            except Exception as e:
                self.logger.error(
                    f"Error running alert {alert.alert_id}", extra={"exception": e}
                )
            self.logger.info(f"Alert {alert.alert_id} ran successfully")
