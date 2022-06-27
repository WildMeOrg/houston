#!/bin/bash

./scripts/utils/clean.sh

# Install the package
./scripts/codex/install.sh

# Build and deploy frontend
./scripts/codex/build.frontend.sh

# Build and deploy Swagger UI
./scripts/swagger/build.sh
