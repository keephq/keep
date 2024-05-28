class ConfigException(Exception):
    """ Exception for configuration errors """
    def __init__(self, messoge: str, *args: object):
        super().__init__(messoge, args)


