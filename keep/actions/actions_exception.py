class ActionsFactoryException(Exception):
    """An exception class that depicts any error comming from Action"""
    def __init__(self, status_code: int, message):
        self.message = message
        self.status_code = status_code