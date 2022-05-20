#!/bin/bash

set -ex

mkdir -p ${DATA_ROOT}

chown nobody ${DATA_ROOT}

source /docker-entrypoint.sh

docker_setup_env

set_up_development_mode

exec gosu nobody bash
