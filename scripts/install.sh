#!/bin/bash

./scripts/venv.sh

source virtualenv/houston3.7/bin/activate

pip install -e ".[testing]"

invoke app.dependencies.install
