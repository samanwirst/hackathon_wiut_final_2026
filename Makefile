PYTHON ?= python3

.PHONY: help check

help:
	@printf '%s\n' 'make check  - validate the repository scaffold (Python 3 required)'

check:
	$(PYTHON) scripts/check_structure.py
