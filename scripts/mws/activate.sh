#!/bin/bash

set -e

./scripts/utils/deactivate.sh
# ./scripts/utils/clean.sh

ln -s .env.mws .env
ln -s config.mws.py config.py
ln -s docker-compose.mws.yml docker-compose.yml
