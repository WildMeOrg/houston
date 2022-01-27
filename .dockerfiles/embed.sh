#!/bin/bash

set -ex

pip install -e ".[testing]"

python setup.py --version
