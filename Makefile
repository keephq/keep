PYTHON=python3

.PHONY: test verify

test:
	$(PYTHON) -m pytest keep/providers/tests/test_squadcast_provider.py

verify: test
