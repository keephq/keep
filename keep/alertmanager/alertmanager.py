from keep.parser.parser import Parser


class AlertManager:
    def __init__(self):
        self.parser = Parser()

    def run(self, file):
        print(f"Running alert {file}")
        self.parser.parse(file)
