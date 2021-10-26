#!/bin/bash -e
# Assumes it is run from the project root.


if [ ! -z ${DEBUG} ]; then
    echo 'DEBUG enabled'
    # Enable execution lines
    set -x
fi

# check to see if this file is being run or sourced from another script
function _is_sourced() {
    # See also https://unix.stackexchange.com/a/215279
    # macos bash source check OR { linux shell check }
    [[ "${#BASH_SOURCE[@]}" -eq 0 ]] || { [ "${#FUNCNAME[@]}" -ge 2 ]  && [ "${FUNCNAME[0]}" = '_is_sourced' ] && [ "${FUNCNAME[1]}" = 'source' ]; }
}

function trap_error_help() {
    set +x
    echo "If you are having issues building:"
    echo " 1. first try 'git submodule update --remote', then ..."
    echo "    if that works, remember to commit the submodule change"
    echo " 2. file an issue"
}

function parse_git_hash() {
    if [ -d _frontend.mws ]; then
        GIT_DIR='_frontend.mws/.git'
    fi
    GIT_DIR=$GIT_DIR git rev-parse --short HEAD 2> /dev/null | sed "s/\(.*\)/\1/"
}

# Get last commit hash prepended with @ (i.e. @8a323d0)
GIT_BRANCH=$(parse_git_hash)
# Copy dist packages out of MWS _frontend repo and deploy
BASE_INSTALL_PATH="app/static/"


function get_install_path() {
    timestamp=$(date '+%Y%m%d-%H%M%S%Z')
    echo "${BASE_INSTALL_PATH}/dist-${GIT_BRANCH}_${timestamp}"
}

function checkout() {
    # Look for a previous submodule checkout prior to initializing
    if [ ! -f _frontend.mws/package.json ]; then
        echo "Checking out  submodules..."
        git submodule update --init --recursive
    fi
}

function build_in_docker() {
    echo "Running the MWS frontend build within Docker..."
    # Ensure the node image is up-to-date
    docker pull node:latest
    docker run --rm -v $(pwd)/:/code -w /code node:latest /bin/bash -c "./scripts/mws/build.frontend.sh --exec"
    echo "Finished running the build within Docker"
}

function build() {
    set -ex

    # Update code
    pushd _frontend.mws/

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
        echo "You will need to edit _frontend.mws/src/constants/apiKeys.js file to get the MWS frontend to run properly."
        cp src/constants/apiKeysTemplate.js src/constants/apiKeys.js
    fi

    # Build dist of the MWS frontend UI
    #  you can alter houston url here if desired
    npm run build -- --env=houston=relative

    # Package
    tar -zcvf dist.${GIT_BRANCH}.tar.gz dist/
    cp dist.${GIT_BRANCH}.tar.gz dist.latest.tar.gz

    popd
}

function install() {
    echo "Installing ..."
    dist_install=$(get_install_path)
    rm -rf ${BASE_INSTALL_PATH}/dist-latest
    mkdir -p ${dist_install}
    tar -zxvf _frontend.mws/dist.latest.tar.gz -C ${dist_install} --strip-components=1
    # Assume dist_install is also in $BASE_INSTALL_PATH
    ln -s $(basename ${dist_install}) ${BASE_INSTALL_PATH}/dist-latest
    echo "Finished Installing"
}

function _main() {
    # Build within a Node container
    if [[ "$1" != "--exec" ]]; then
        trap trap_error_help ERR
        checkout
        build_in_docker
        install
        exit $?
    else
        build
    fi
}

if ! _is_sourced; then
    _main "$@"
fi
