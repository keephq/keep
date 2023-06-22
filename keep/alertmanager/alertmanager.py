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
                try:
                    self._run(alerts_path, providers_file)
                except Exception:
                    self.logger.exception("Error running alert in interval mode")
                self.logger.info(f"Sleeping for {interval} seconds...")
                time.sleep(interval)
        # If interval is not set, run the alert once
        else:
            errors = self._run(alerts_path, providers_file)
        # TODO: errors should be part of the Alert/Action/Step class so it'll be distinguishable
        if any(errors):
            self.logger.error(
                f"Alert(s) from {alerts_path} ran with errors",
                extra={"interval": interval},
            )
            raise Exception("Alert(s) ran with errors")
        else:
            self.logger.info(
                f"Alert(s) from {alerts_path} ran successfully",
                extra={"interval": interval},
            )

    def get_alerts(
        self, alert_path: str | tuple[str], providers_file: str = None
    ) -> list[Alert]:
        alerts = []
        if isinstance(alert_path, tuple):
            for alert_url in alert_path:
                alerts.extend(self.parser.parse(alert_url, providers_file))
        elif os.path.isdir(alert_path):
            alerts.extend(self._get_alerts_from_directory(alert_path, providers_file))
        else:
            alerts = self.parser.parse(alert_path, providers_file)
        return alerts

    def _run(self, alert_path: str | tuple[str], providers_file: str = None):
        alerts = self.get_alerts(alert_path, providers_file)
        errors = self._run_alerts(alerts)
        return errors

    def _get_alerts_from_directory(
        self, alerts_dir: str, providers_file: str = None
    ) -> list[Alert]:
        """
        Run alerts from a directory.

        Args:
            alerts_dir (str): A directory containing alert yamls.
            providers_file (str, optional): The path to the providers yaml. Defaults to None.
        """
        alerts = []
        for file in os.listdir(alerts_dir):
            if file.endswith(".yaml") or file.endswith(".yml"):
                self.logger.info(f"Getting alerts from {file}")
                try:
                    alerts.extend(
                        self.parser.parse(
                            os.path.join(alerts_dir, file), providers_file
                        )
                    )
                    self.logger.info(f"Alert from {file} fetched successfully")
                except Exception as e:
                    self.logger.error(
                        f"Error parsing alert from {file}", extra={"exception": e}
                    )
        return alerts

    def _run_alerts(self, alerts: typing.List[Alert]):
        alerts_errors = []
        for alert in alerts:
            # otherwise any(errors) might throw an exception
            errors = []
            self.logger.info(f"Running alert {alert.alert_id}")
            try:
                errors = alert.run()
            except Exception as e:
                self.logger.error(
                    f"Error running alert {alert.alert_id}", extra={"exception": e}
                )
                if alert.on_failure:
                    self.logger.info(
                        f"Running on_failure action for alert {alert.alert_id}"
                    )
                    # Adding the exception message to the provider context so it'll be available for the action
                    message = (
                        f"Alert `{alert.alert_id}` failed with exception: `{str(e)}`"
                    )
                    alert.on_failure.provider_context = {"message": message}
                    alert.on_failure.run()
                raise
            if any(errors):
                self.logger.info(msg=f"Alert {alert.alert_id} ran with errors")
            else:
                self.logger.info(f"Alert {alert.alert_id} ran successfully")
            alerts_errors.extend(errors)
        return alerts_errors

    def run_step(self, alert_id: str, step: str):
        self.logger.info(f"Running step {step} of alert {alert.alert_id}")
        try:
            alert = self.get_alerts(alert_id)
            alert.run_step(step)
        except Exception as e:
            self.logger.error(
                f"Error running step {step} of alert {alert.alert_id}",
                extra={"exception": e},
            )
        self.logger.info(f"Step {step} of alert {alert.alert_id} ran successfully")
