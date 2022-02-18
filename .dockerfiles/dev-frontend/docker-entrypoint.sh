#!/bin/bash

set -ex

cd /code/_frontend.${HOUSTON_APP_CONTEXT}
npm install --legacy-peer-deps
export NODE_ENV=development
npx webpack serve --config ./config/webpack/webpack.common.js --host $HOST --public ${HOST}:${PORT} --env=houston=relative
