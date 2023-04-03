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



