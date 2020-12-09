#!/bin/bash

git checkout next
git pull
./scripts/build.docker.sh
./scripts/run.sh
