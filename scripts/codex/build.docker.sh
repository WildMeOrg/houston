#!/bin/bash

docker build --build-arg PROJECT="codex" --tag wildme/codex:latest --target main .
