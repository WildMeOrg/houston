#!/bin/bash

./scripts/build.sh
./scripts/host.export.sh
ssh -t houston '/opt/houston/host.run.sh'
./scripts/host.monitor.sh
