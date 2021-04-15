#!/bin/bash

./scripts/clean.sh

# Install the package
./scripts/install.sh

# Build and deploy frontend
./scripts/build.frontend.sh

# Build and deploy Swagger UI
./scripts/build.swagger.sh

# Build docker image
./scripts/build.docker.sh
