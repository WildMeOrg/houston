#!/bin/bash

./scripts/venv.sh

source virtualenv/houston3.7/bin/activate

pip install -r requirements.txt
pip install -e .

invoke app.dependencies.install
