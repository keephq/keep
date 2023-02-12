---
sidebar_label: Adding a New Provider
sidebar_position: 2
---

# ➕ New Provider

### Basics

- BaseProvider is the base class every provider should inherit from
- BaseProvider exposes 4 important functions:
  - `query(self, **kwargs: dict)` which is used to query the provider in steps
  - `notify(self, **kwargs: dict)` which is used to notify via the provider in actions
  - `dispose(self)` which is used to dispose the provider after usage (e.g. close the connection to the DB)
  - `validate_config(self)` which is used to validate the configuration passed to the Provider
- Providers must be located in the providers directory
- Provider directory must start with the provider's unique identifier followed by underscore+provider (e.g. `slack_provider`)
- Provider file name must start with the provider's unique identifier followed by underscore+provider+.py (e.g. `slack_provider.py`)

### ProviderConfig
```python
@dataclass
class ProviderConfig:
    """
    Provider configuration model.

    Args:
        description (Optional[str]): The description of the provider.
        authentication (dict): The configuration for the provider.
    """

    authentication: dict
    description: Optional[str] = None

    def __post_init__(self):
        if not self.authentication:
            return
        for key, value in self.authentication.items():
            if (
                isinstance(value, str)
                and value.startswith("{{")
                and value.endswith("}}")
            ):
                self.authentication[key] = chevron.render(value, {"env": os.environ})
```

### BaseProvider

```python
class BaseProvider(metaclass=abc.ABCMeta):
    def __init__(self, provider_id: str, config: ProviderConfig):
        """
        Initialize a provider.

        Args:
            provider_id (str): The provider id.
            **kwargs: Provider configuration loaded from the provider yaml file.
        """
        # Initalize logger for every provider
        self.logger = logging.getLogger(self.__class__.__name__)
        self.id = provider_id
        self.config = config
        self.validate_config()
        self.logger.debug(
            "Base provider initalized", extra={"provider": self.__class__.__name__}
        )

    @property
    def provider_id(self) -> str:
        """
        Get the provider id.

        Returns:
            str: The provider id.
        """
        return self.id

    @abc.abstractmethod
    def dispose(self):
        """
        Dispose of the provider.
        """
        raise NotImplementedError("dispose() method not implemented")

    @abc.abstractmethod
    def validate_config():
        """
        Validate provider configuration.
        """
        raise NotImplementedError("validate_config() method not implemented")

    def notify(self, **kwargs):
        """
        Output alert message.

        Args:
            **kwargs (dict): The provider context (with statement)
        """
        raise NotImplementedError("notify() method not implemented")

    def query(self, **kwargs: dict):
        """
        Query the provider using the given query

        Args:
            kwargs (dict): The provider context (with statement)

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("query() method not implemented")
```
