import pytest

from keep.exceptions.config_exception import ConfigException
from keep.providers.cloudwatch_provider.cloudwatch_provider import CloudwatchProvider
import logging


@pytest.mark.parametrize(
    "wh_url, api_key, expected_result, expected_exception",
    [
        ("http://test_utl", "1212s", "http://api_key:1212s@test_utl", None),
        ("https://test_utl", "1212s", "https://api_key:1212s@test_utl", None),
        ("wronghttp://api_key:1212s@test_utl", "1212s", None, ConfigException)
    ]
)
def test_add_credentials_to_wh_url(wh_url, api_key, expected_result, expected_exception):
    if expected_exception:
        with pytest.raises(expected_exception):
            url = CloudwatchProvider.add_credentials_to_wh_url(
                logging.getLogger(__file__),
                webhook_url=wh_url,
                api_key=api_key
            )
    else:
        url = CloudwatchProvider.add_credentials_to_wh_url(
            logging.getLogger(__file__),
            webhook_url=wh_url,
            api_key=api_key
        )
        assert url == expected_result