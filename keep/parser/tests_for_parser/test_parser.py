# here we are going to create all needed tests for the parser.py parse function
import pytest
import requests

from keep.parser.parser import Parser


def test_parse_with_nonexistent_file():
    parser = Parser()
    # Expected error when a given input does not describe an existing file
    with pytest.raises(FileNotFoundError):
        parser.parse('non-existing-file')


def test_parse_with_nonexistent_url():
    parser = Parser()
    # Expected error when a given input does not describe an existing URL
    with pytest.raises(requests.exceptions.ConnectionError):
        parser.parse('https://ThisWebsiteDoNotExist.com')


def test_parse_sanity_check():
    parser = Parser()
    providers_path = 'keep/parser/tests_for_parser/resources/providers_for_testing.yaml'
    alert_path = 'keep/parser/tests_for_parser/resources/db_disk_space_for_testing.yml'
    parsed_alerts = parser.parse(alert_path,providers_path)
    assert parsed_alerts is not None
    assert len(parsed_alerts) > 0, "caution: the expected output is a list with at least one alert, instead got non "
    for index, parse_alert in enumerate(parsed_alerts):
        print('validating parsed alert #' + str(index+1) + ' out of ' + str(len(parsed_alerts)))
        assert len(parse_alert.alert_actions) > 0
        assert parse_alert.alert_file.endswith('.yml') or parse_alert.alert_file.endswith('.yaml')
        assert parse_alert.alert_source.endswith('.yml') or parse_alert.alert_source.endswith('.yaml')
        assert parse_alert.alert_id is not None
        assert len(parse_alert.alert_owners) > 0 and all(parse_alert.alert_owners)
        assert len(parse_alert.alert_tags) > 0 and all(isinstance(item, str) for item in parse_alert.alert_tags)












