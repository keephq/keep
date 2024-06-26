import pytest
from unittest.mock import patch, Mock
from keep.providers.servicenow.servicenow_provider import ServiceNowProvider

@pytest.fixture
def servicenow_provider():
    return ServiceNowProvider('https://your_instance.service-now.com', 'your_username', 'your_password')

@patch('keep.providers.servicenow.servicenow_provider.requests.Session.get')
def test_fetch_incidents(mock_get, servicenow_provider):
    # Mock the API response
    mock_response = Mock()
    mock_response.json.return_value = {
        'result': [
            {
                'sys_id': '1',
                'short_description': 'Test Incident 1',
                'description': 'Description of Test Incident 1',
                'sys_created_on': '2023-06-01 00:00:00',
                'sys_updated_on': '2023-06-02 00:00:00',
                # Add other necessary fields
            },
            {
                'sys_id': '2',
                'short_description': 'Test Incident 2',
                'description': 'Description of Test Incident 2',
                'sys_created_on': '2023-06-03 00:00:00',
                'sys_updated_on': '2023-06-04 00:00:00',
                # Add other necessary fields
            }
        ]
    }
    mock_get.return_value = mock_response

    incidents = servicenow_provider.fetch_incidents()
    
    assert len(incidents) == 2
    assert incidents[0]['id'] == '1'
    assert incidents[0]['title'] == 'Test Incident 1'

@patch('keep.providers.servicenow.servicenow_provider.requests.Session.get')
def test_process_incidents(mock_get, servicenow_provider):
    # Mock the API response
    mock_response = Mock()
    mock_response.json.return_value = {
        'result': [
            {
                'sys_id': '1',
                'short_description': 'Test Incident 1',
                'description': 'Description of Test Incident 1',
                'sys_created_on': '2023-06-01 00:00:00',
                'sys_updated_on': '2023-06-02 00:00:00',
                # Add other necessary fields
            }
        ]
    }
    mock_get.return_value = mock_response

    incidents = servicenow_provider.fetch_incidents()
    
    assert len(incidents) == 1
    assert incidents[0]['id'] == '1'
    assert incidents[0]['title'] == 'Test Incident 1'
    assert incidents[0]['description'] == 'Description of Test Incident 1'
