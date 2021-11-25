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

# Copy dist packages out of _swagger-ui
BASE_INSTALL_PATH="app/static/swagger-ui/"
# Package source resides in...
SOURCE_PATH="_swagger-ui"

function build_in_docker() {
    echo "Running the Swagger build within Docker..."
    docker pull node:lts
    docker run --rm -v $(pwd)/:/code -w /code node:lts /bin/bash -c "./scripts/swagger/build.sh --exec"
    echo "Finished running the build within Docker"
}

function build() {
    # Update code
    pushd "${SOURCE_PATH}"

    # Remove any pre-downloaded modules
    rm -rf node_modules/
    rm -rf package-lock.json
    rm -rf swagger_static/

    mkdir -p swagger_static/

    # Install dependencies fresh
    npm cache clean -f

    npm install -g npm@latest

    npm install --legacy-peer-deps

    npm audit fix --force

    # Copy files
    cp node_modules/swagger-ui-dist/{swagger-ui*.{css,js}{,.map},favicon*.png,oauth2-redirect.html} swagger_static/

    cp node_modules/typeface-droid-sans/index.css swagger_static/droid-sans.css

    cp -R node_modules/typeface-droid-sans/files swagger_static/

    popd
}

function install() {
    echo "Installing ..."
    rm -rf ${BASE_INSTALL_PATH}

    mkdir -p ${BASE_INSTALL_PATH}

    cp -R ${SOURCE_PATH}/swagger_static/* ${BASE_INSTALL_PATH}
    echo "Finished Installing"
}

# Build within a Node container

function _main() {
    # Build within a Node container
    if [[ "$1" != "--exec" ]]; then
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
