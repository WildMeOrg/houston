#!/bin/bash

set -e

timeout=${TIMEOUT-20}
poll_frequency=${POLL_FREQUENCY-1}
url=${CODEX_URL}
admin_email=${ADMIN_EMAIL-'root@example.org'}
admin_password=${ADMIN_PASSWORD-password}
admin_name=${ADMIN_NAME-'Test admin'}
site_name=${SITE_NAME-'Mytestsite'}
browser=${BROWSER-chrome}
use_headless=${BROWSER_HEADLESS-true}


function print_help(){
  cat <<EOF
Usage: ${0} ARGS

Arguments:
  --url   - URL to the target deployment
  -u | --admin-email   - administrative email address
  -p | --admin-password   - administrative password
  --admin-name   - administrative name
  --site-name   - site name

EOF
}


for arg in $@
do
  case $arg in
    --url)
      url="$2"
      shift
      shift
    ;;
    -u|--admin-email)
      admin_email="$2"
      shift
      shift
    ;;
    -p|--admin-password)
      admin_password="$2"
      shift
      shift
      ;;
    --admin-name)
      admin_name="$2"
      shift
      shift
      ;;
    --site-name)
      site_name="$2"
      shift
      shift
      ;;
    [?])
      echo "Invalid Argument Passed: $arg"
      print_help
      exit 1
    ;;
  esac
done


script="
apt update
apt install -y python3-pip
pip install -r /code/integration_tests/requirements.txt
pytest -vv -x /code/integration_tests
"


function main() {
  if [ -z "$url" ]; then
    print_help
    exit 1
  fi

  docker run --rm \
    -it \
    -e TIMEOUT="$timeout" \
    -e POLL_FREQUENCY="$poll_frequency" \
    -e CODEX_URL="$url" \
    -e ADMIN_EMAIL="$admin_email" \
    -e ADMIN_PASSWORD="$admin_password" \
    -e ADMIN_NAME="$admin_name" \
    -e SITE_NAME="$site_name" \
    -e BROWSER="$browser" \
    -e BROWSER_HEADLESS="$use_headless" \
    -v ${PWD}/integration_tests:/code/integration_tests \
    -v ${PWD}/tests:/code/tests \
    -w /code \
    -u root \
    --entrypoint sh \
    selenium/standalone-chrome \
    -c "$script"
  exit $?
}


# check to see if this file is being run or sourced from another script
function _is_sourced() {
  # See also https://unix.stackexchange.com/a/215279
  # macos bash source check OR { linux shell check }
  [[ "${#BASH_SOURCE[@]}" -eq 0 ]] || { [ "${#FUNCNAME[@]}" -ge 2 ]  && [ "${FUNCNAME[0]}" = '_is_sourced' ] && [ "${FUNCNAME[1]}" = 'source' ]; }
}


if ! _is_sourced; then
  main "$@"
fi
