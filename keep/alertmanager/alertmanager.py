import logging
import os
import threading
import time
import typing

from keep.alert.alert import Alert
from keep.alertmanager.alertcheduler import AlertScheduler
from keep.contextmanager.contextmanager import ContextManager
from keep.parser.parser import Parser


class AlertManager:
    def __init__(self, interval: int = 0):
        self.logger = logging.getLogger(__name__)
        self.scheduler = AlertScheduler(self)
        self.context_manager = ContextManager.get_instance()
        self.default_interval = interval
        self.scheduler_mode = False

    def stop(self):
        if self.scheduler_mode:
            self.logger.info("Stopping alert manager")
            self.context_manager.dump()
            self.scheduler.stop()
            self.logger.info("Alert manager stopped")
        else:
            pass

    def run(self, alerts: list[Alert]):
        """
        Run alerts from a file or directory.

        Args:
            alert (str): Either an alert yaml or a directory containing alert yamls or a list of URLs to get the alerts from.
            providers_file (str, optional): The path to the providers yaml. Defaults to None.
        """
        self.logger.info(f"Running alert(s)")
        alerts_errors = []
        # If at least one alert has an interval, run alerts using the scheduler,
        #   otherwise, just run it
        if self.default_interval or any([alert.alert_interval for alert in alerts]):
            # running alerts in scheduler mode
            self.logger.info(
                "Found at least one alert with an interval, running in scheduler mode"
            )
            self.scheduler_mode = True
            # if the alerts doesn't have an interval, set the default interval
            for alert in alerts:
                alert.alert_interval = alert.alert_interval or self.default_interval
            # This will halt until KeyboardInterrupt
            self.scheduler.run_alerts(alerts)
            self.logger.info("Alert(s) scheduled")
        else:
            # running alerts in the regular mode
            alerts_errors = self._run_alerts(alerts)

        return alerts_errors

    def _run_alert(self, alert: Alert):
        self.logger.info(f"Running alert {alert.alert_id}")
        errors = []
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
                message = f"Alert `{alert.alert_id}` failed with exception: `{str(e)}`"
                alert.on_failure.provider_parameters = {"message": message}
                alert.on_failure.run()
            raise
        if any(errors):
            self.logger.info(msg=f"Alert {alert.alert_id} ran with errors")
        else:
            self.logger.info(f"Alert {alert.alert_id} ran successfully")
        return errors

    def _run_alerts(self, alerts: typing.List[Alert]):
        alerts_errors = []
        for alert in alerts:
            try:
                errors = self._run_alert(alert)
                alerts_errors.append(errors)
            except Exception as e:
                self.logger.error(
                    f"Error running alert {alert.alert_id}", extra={"exception": e}
                )
                raise

        return alerts_errors
