#!/bin/bash
# Assumes it is run from the project root.

set -e

if [ ! -d "_frontend" ]; then
    echo "Checking out  submodules..."
    git submodule update --init --recursive
fi

# Build within a Node container
if [[ "$1" != "--exec" ]]; then
    echo "Running the frontend build within Docker..."
    docker run -v $(pwd)/:/code -w /code node:latest /bin/bash -c "./scripts/build.frontend.sh --exec"
    echo "Finished running the build within Docker"
    exit $?
fi

set -ex

# Get last commit hash prepended with @ (i.e. @8a323d0)
function parse_git_hash() {
  git rev-parse --short HEAD 2> /dev/null | sed "s/\(.*\)/\1/"
}

function parse_datetime() {
  date '+%Y%m%d-%H%M%S%Z'
}

# Update code
cd _frontend/

# Get current commit hash
GIT_BRANCH=$(parse_git_hash)
TIMESTAMP=$(parse_datetime)

echo "Building with Git hash = ${GIT_BRANCH} with timestamp = ${TIMESTAMP}"

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
npm run build -- --houston ""

# Package
tar -zcvf dist.${GIT_BRANCH}.${TIMESTAMP}.tar.gz dist/
cp dist.${GIT_BRANCH}.${TIMESTAMP}.tar.gz dist.latest.tar.gz
cd ../

# Copy dist packages out of _frontend repo and deploy
DEST_FOLDER="dist-${GIT_BRANCH}-${TIMESTAMP}/"
DEST_PATH="app/static/${DEST_FOLDER}"

cp _frontend/dist.*.tar.gz ./
rm -rf app/static/dist-latest
mkdir -p ${DEST_PATH}
tar -zxvf dist.latest.tar.gz -C ${DEST_PATH} --strip-components=1
ln -s ${DEST_FOLDER} app/static/dist-latest
