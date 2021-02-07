#!/bin/bash

./scripts/clean.sh

pip install -r requirements.txt

python setup.py develop

pip install -e .
