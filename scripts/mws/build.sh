#!/bin/bash

./scripts/utils/clean.sh

# Install the package
./scripts/mws/install.sh

# Build and deploy frontend
./scripts/mws/build.frontend.sh

# Build and deploy Swagger UI
./scripts/swagger/build.sh

# Build docker image
./scripts/mws/build.docker.sh
