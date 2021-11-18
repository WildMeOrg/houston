#!/bin/bash

docker build --build-arg PROJECT="mws" --tag wildme/mws:latest --target main .
