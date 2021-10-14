#!/bin/bash

set -e

./scripts/utils/deactivate.sh

ln -s .env.codex .env
ln -s config.codex.py config.py
ln -s docker-compose.codex.yml docker-compose.yml
