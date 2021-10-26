#!/bin/bash

./scripts/venv.sh

source virtualenv/mws/bin/activate

pip install -e ".[testing]"

invoke dependencies.install-python-dependencies
