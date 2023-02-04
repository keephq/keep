import logging

from keep.parser.parser import Parser


class AlertManager:
    def __init__(self):
        self.parser = Parser()
        self.logger = logging.getLogger(__name__)

    def run(self, alert_file: str, hosts_directory: str = None):
        self.logger.info(f"Running alert {alert_file}")
        alert = self.parser.parse(alert_file, hosts_directory)
        alert.run()
        self.logger.info(f"Alert {alert_file} ran successfully")
