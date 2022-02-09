#!/usr/bin/env bash
set -Eeo pipefail

curl -f "http://0.0.0.0:5000/api/v1/site-settings/heartbeat" -H "Host: $SERVER_NAME"
