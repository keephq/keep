import logging
import os

from keep.parser.parser import Parser


class AlertManager:
    def __init__(self):
        self.parser = Parser()
        self.logger = logging.getLogger(__name__)

    def run(self, alert: str, providers_file: str = None):
        """
        Run alerts from a file or directory.

        Args:
            alert (str): Either a an alert yaml or a directory containing alert yamls.
            providers_file (str, optional): The path to the providers yaml. Defaults to None.
        """
        self.logger.info(f"Running alert(s) from {alert}")
        if os.path.isdir(alert):
            self.run_from_directory(alert, providers_file)
        else:
            alert = self.parser.parse(alert, providers_file)
            alert.run()
        self.logger.info(f"Alert(s) from {alert} ran successfully")

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
                    alert = self.parser.parse(os.path.join(alert, file), providers_file)
                    alert.run()
                    self.logger.info(f"Alert from {file} ran successfully")
                except Exception as e:
                    self.logger.error(
                        f"Error running alert from {file}", extra={"exception": e}
                    )
