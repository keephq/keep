from keep.parser.parser import Parser


class AlertManager:
    def __init__(self):
        self.parser = Parser()

    def run(self, alert_file: str, hosts_directory: str = None):
        print(f"Running alert {alert_file}")
        self.parser.parse(alert_file, hosts_directory)
