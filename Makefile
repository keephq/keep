.PHONY: verify test lint

verify: lint test

test:
	python -m pytest tests/test_squadcast_provider.py -v

lint:
	python -m py_compile keep/providers/squadcast_provider/squadcast_provider.py
	python -m py_compile keep/providers/squadcast_provider/__init__.py
