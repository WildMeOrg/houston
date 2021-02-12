#!/bin/bash
# Assumes it is run from the project root.

set -e

# Get last commit hash prepended with @ (i.e. @8a323d0)
GIT_BRANCH=$(git rev-parse --short HEAD 2> /dev/null | sed "s/\(.*\)/\1/")
# Copy dist packages out of _frontend repo and deploy
BASE_INSTALL_PATH="app/static/"


function get_install_path() {
    timestamp=$(date '+%Y%m%d-%H%M%S%Z')
    echo "${BASE_INSTALL_PATH}/dist-${GIT_BRANCH}_${timestamp}"
}

function checkout() {
    # Look for a previous submodule checkout prior to initializing
    if [ ! -d _frontend/package.json ]; then
        echo "Checking out  submodules..."
        git submodule update --init --recursive
    fi
}

function build_in_docker() {
    echo "Running the frontend build within Docker..."
    docker run --rm -v $(pwd)/:/code -w /code node:latest /bin/bash -c "./scripts/build.frontend.sh --exec"
    echo "Finished running the build within Docker"
}

function build() {
    set -ex

    # Update code
    pushd _frontend/

    echo "Building with Git hash = ${GIT_BRANCH}"

    # Remove any pre-downloaded modules
    rm -rf node_modules/
    rm -rf package-lock.json
    rm -rf dist/
    rm -rf dist.*.tar.gz

    # Install dependencies fresh
    npm install

    # Create API file, if it doesn't exist
    if [[ ! -f src/constants/apiKeys.js ]]
    then
        echo "Copying apiKeysTemplate.js to apiKeys.js..."
        echo "You will need to edit _frontend/src/constants/apiKeys.js file to get the frontend to run properly."
        cp src/constants/apiKeysTemplate.js src/constants/apiKeys.js
    fi

    # Build dist of the frontend UI
    #  you can alter houston url here if desired
    npm run build -- --env=houston=relative

    # Package
    tar -zcvf dist.${GIT_BRANCH}.tar.gz dist/
    cp dist.${GIT_BRANCH}.tar.gz dist.latest.tar.gz

    popd
}

function install() {
    dist_install=$(get_install_path)
    rm -rf app/static/dist-latest
    mkdir -p ${dist_install}
    tar -zxvf _frontend/dist.latest.tar.gz -C ${dist_install} --strip-components=1
    ln -s ${dist_install} app/static/dist-latest
}

# Build within a Node container
if [[ "$1" != "--exec" ]]; then
    checkout
    build_in_docker
    install
    exit $?
else
    build
fi
