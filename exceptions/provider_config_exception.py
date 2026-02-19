class ProviderConfigException(Exception):
    def __init__(self, message, provider_id, *args: object) -> None:
        super().__init__(message, *args)
        self.provider_id = provider_id
