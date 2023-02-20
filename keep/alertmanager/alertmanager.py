import logging
import os

from keep.parser.parser import Parser


class AlertManager:
    def __init__(self):
        self.parser = Parser()
        self.logger = logging.getLogger(__name__)

    def run(self, alert_file: str, providers_file: str = None):
        """
        Run alerts from a file or directory.

        Args:
            alert_file (str): Either a an alert yaml or a directory containing alert yamls.
            providers_file (str, optional): The path to the providers yaml. Defaults to None.
        """
        self.logger.info(f"Running alert(s) from {alert_file}")
        if os.path.isdir(alert_file):
            for file in os.listdir(alert_file):
                if file.endswith(".yaml") or file.endswith(".yml"):
                    self.logger.info(f"Running alert from {file}")
                    try:
                        alert = self.parser.parse(
                            os.path.join(alert_file, file), providers_file
                        )
                        alert.run()
                        self.logger.info(f"Alert from {file} ran successfully")
                    except Exception as e:
                        self.logger.error(
                            f"Error running alert from {file}", extra={"exception": e}
                        )
        else:
            alert = self.parser.parse(alert_file, providers_file)
            alert.run()
        self.logger.info(f"Alert(s) from {alert_file} ran successfully")
