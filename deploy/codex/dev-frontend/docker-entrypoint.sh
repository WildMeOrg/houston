#!/bin/bash

set -ex

npm install
export NODE_ENV=development
npx webpack serve --config ./config/webpack/webpack.common.js --host $HOST --public ${HOST}:${PORT} --env=houston=relative
