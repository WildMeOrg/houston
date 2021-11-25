#!/bin/bash

DOCKER_BUILDKIT=1 docker build --target main --tag wildme/houston:latest .
