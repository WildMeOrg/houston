#!/bin/bash

./scripts/codex/venv.sh

source virtualenv/codex/bin/activate

pip install -e ".[testing]"

invoke dependencies.install-python-dependencies
