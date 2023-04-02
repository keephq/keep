# here we are going to create all needed tests for the parser.py parse function
import pytest
import requests

from keep.parser.parser import Parser


def test_parse_with_nonexistent_file():
    self = Parser()
    # Expected error when a given input does not describe an existing file
    with pytest.raises(FileNotFoundError):
        self.parse('')


def test_parse_with_nonexistent_url():
    self = Parser()
    # Expected error when a given input does not describe an existing URL
    with pytest.raises(requests.exceptions.ConnectionError):
        self.parse('https://ThisWebsiteDoNotExist.com')



