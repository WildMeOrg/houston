#!/bin/bash
# Assumes it is run from the project root.

set -e

function parse_git_hash() {
    if [ -d _frontend ]; then
        GIT_DIR='_frontend/.git'
    fi
    GIT_DIR=$GIT_DIR git rev-parse --short HEAD 2> /dev/null | sed "s/\(.*\)/\1/"
}

# Get last commit hash prepended with @ (i.e. @8a323d0)
GIT_BRANCH=$(parse_git_hash)
# Copy dist packages out of _frontend repo and deploy
BASE_INSTALL_PATH="app/static/"


function get_install_path() {
    timestamp=$(date '+%Y%m%d-%H%M%S%Z')
    echo "${BASE_INSTALL_PATH}/dist-${GIT_BRANCH}_${timestamp}"
}

function checkout() {
    set -ex

    # Look for a previous submodule checkout prior to initializing
    if [ ! -f _frontend/package.json ]; then
        echo "Checking out submodules..."
        git submodule update --init --recursive
    fi
}

function build_in_docker() {
    set -ex

    echo "Running the frontend build within Docker..."
    docker pull node:latest
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
    npm cache clean -f

    npm install -g npm@latest

    npm install --legacy-peer-deps

    npm audit fix --force

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
    rm -rf ${BASE_INSTALL_PATH}/dist-latest
    mkdir -p ${dist_install}
    tar -zxvf _frontend/dist.latest.tar.gz -C ${dist_install} --strip-components=1
    # Assume dist_install is also in $BASE_INSTALL_PATH
    ln -s $(basename ${dist_install}) ${BASE_INSTALL_PATH}/dist-latest
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
