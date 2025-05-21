#!/bin/bash
# Run all tests with correct environment and import path
export PYTHONPATH=src
pytest src/tests/ --maxfail=3 --disable-warnings -v 