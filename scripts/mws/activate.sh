#!/bin/bash

set -e

./scripts/utils/deactivate.sh
# ./scripts/utils/clean.sh

ln -s docker-compose.mws.yml docker-compose.yml
