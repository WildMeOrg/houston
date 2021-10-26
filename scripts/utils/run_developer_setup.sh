#!/bin/bash

./scripts/utils/clean.sh

pip install -e ".[testing]"
