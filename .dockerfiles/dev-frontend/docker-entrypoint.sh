#!/bin/bash

set -ex

# If the submodule directory name exists, move to it.
# Otherwise assume the frontend is the current working directory
if [ -d "_frontend.${HOUSTON_APP_CONTEXT}" ]; then
    cd /code/_frontend.${HOUSTON_APP_CONTEXT}
fi
npm install --legacy-peer-deps
export NODE_ENV=development
npx webpack serve --config ./config/webpack/webpack.common.js --host $HOST --public ${HOST}:${PORT} --env=houston=relative
