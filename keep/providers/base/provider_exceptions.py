class GetAlertException(Exception):
    def __init__(self, message, status_code=403):
        self.message = message
        self.status_code = status_code
