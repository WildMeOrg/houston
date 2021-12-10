#!/bin/bash

set -ex

npm install --legacy-peer-deps
export NODE_ENV=development
npx webpack serve --config ./config/webpack/webpack.common.js --host $HOST --public ${HOST}:${PORT} --env=houston=relative
