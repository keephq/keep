import logging
import threading
import time
import typing

from keep.alert.alert import Alert


class AlertScheduler:
    def __init__(self, alert_manager):
        self.logger = logging.getLogger(__name__)
        self.threads = []
        self.alert_manager = alert_manager
        self._stop = False

    def run_alerts(self, alerts: typing.List[Alert]):
        for alert in alerts:
            thread = threading.Thread(
                target=self._run_alerts_with_interval,
                args=[alert],
                daemon=True,
            )
            thread.start()
            self.threads.append(thread)
        # as long as the stop flag is not set, sleep
        while not self._stop:
            time.sleep(1)

    def stop(self):
        self.logger.info("Stopping scheduled alerts")
        self._stop = True
        # Now wait for the threads to finish
        for thread in self.threads:
            thread.join()
        self.logger.info("Scheduled alerts stopped")

    def _run_alerts_with_interval(
        self,
        alert: Alert,
    ):
        """Simple scheduling of alerts with interval

        TODO: Use https://github.com/agronholm/apscheduler

        Args:
            alert (Alert): The alert to run.
        """
        while True and not self._stop:
            self.logger.info(f"Running alert {alert.alert_id}...")
            try:
                self.alert_manager._run_alert(alert)
            except Exception as e:
                self.logger.exception(f"Failed to run alert {alert.alert_id}...")
            self.logger.info(f"Alert {alert.alert_id} ran")
            if alert.alert_interval > 0:
                self.logger.info(f"Sleeping for {alert.alert_interval} seconds...")
                time.sleep(alert.alert_interval)
            else:
                self.logger.info("Alert will not run again")
                break
