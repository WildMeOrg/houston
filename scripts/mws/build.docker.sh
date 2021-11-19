#!/bin/bash

# Use docker buildkit, because it allows for skipping unused stages
# in a multi-stage build. We target using the 'main' build stage
# and ignore the other build stages
DOCKER_BUILDKIT=1 docker build --target main --tag wildme/mws:latest .
