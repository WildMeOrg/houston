#!/bin/bash

set -ex

source /docker-entrypoint.sh

docker_setup_env

set_up_development_mode
