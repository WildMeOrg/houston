#!/bin/bash

set -e

./scripts/utils/deactivate.sh
# ./scripts/utils/clean.sh

ln -s docker-compose.codex.yml docker-compose.yml
