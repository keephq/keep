import logging

from keep.parser.parser import Parser


class AlertManager:
    def __init__(self):
        self.parser = Parser()
        self.logger = logging.getLogger(__name__)

    def run(self, alert_file: str, providers_file: str = None):
        self.logger.info(f"Running alert {alert_file}")
        alert = self.parser.parse(alert_file, providers_file)
        alert.run()
        self.logger.info(f"Alert {alert_file} ran successfully")
