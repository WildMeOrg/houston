#!/usr/bin/env bash
set -Eeo pipefail

# usage: file_env VAR [DEFAULT]
#    ie: file_env 'XYZ_DB_PASSWORD' 'example'
# (will allow for "$XYZ_DB_PASSWORD_FILE" to fill in the value of
#  "$XYZ_DB_PASSWORD" from a file, especially for ** Docker's secrets feature **)
file_env() {
	local var="$1"
	local fileVar="${var}_FILE"
	local def="${2:-}"
	if [ "${!var:-}" ] && [ "${!fileVar:-}" ]; then
		echo >&2 "error: both $var and $fileVar are set (but are exclusive)"
		exit 1
	fi
	local val="$def"
	if [ "${!var:-}" ]; then
		val="${!var}"
	elif [ "${!fileVar:-}" ]; then
		val="$(< "${!fileVar}")"
	fi
	export "$var"="$val"
	unset "$fileVar"
}

# check to see if this file is being run or sourced from another script
_is_sourced() {
	# https://unix.stackexchange.com/a/215279
	[ "${#FUNCNAME[@]}" -ge 2 ] \
		&& [ "${FUNCNAME[0]}" = '_is_sourced' ] \
		&& [ "${FUNCNAME[1]}" = 'source' ]
}

# Loads various settings that are used elsewhere in the script
# This should be called before any other functions
docker_setup_env() {
	file_env 'EDM_AUTHENTICATIONS_0_PASSWORD'
	file_env 'GITLAB_REMOTE_LOGIN_PAT'
	file_env 'SECRET_KEY'
	file_env 'SQLALCHEMY_DATABASE_URI'

	declare -g ALREADY_INITIALIZED
	# look specifically for a dictory that marks the data as initialized
	if [ -d "${DATA_ROOT}/submissions" ]; then
		ALREADY_INITIALIZED='true'
	fi
}

_main() {
	# if first arg looks like a flag, assume we want to run postgres server
	if [ "${1:0:1}" = '-' ]; then
		set -- invoke app.run "$@"
	fi

	# Assume if invoke or wait-for is the first argument,
	# then the service is set to run
	if [ "$1" = 'invoke' ] || [ "$1" = 'wait-for' ]; then
		docker_setup_env
		# only run initialization on an empty data directory
		if [ -z "$ALREADY_INITIALIZED" ]; then
			mkdir -p ${DATA_ROOT}
			# fix permissions on the data directory
			chown nobody ${DATA_ROOT}
			# check dir permissions to reduce likelihood of half-initialized database
			ls ${DATA_ROOT}/ > /dev/null

			# Have the application initialize the data location and database
			# FIXME: `--no-backup` is necessary because this apparently has the side-effect
			#        of doing doing a backup for a database it may not know how to backup.
			gosu nobody invoke app.db.upgrade --no-backup
			# Assume a possible need to initialize the EDM admin user
			gosu nobody invoke app.initialize.initialize-edm-admin-user

			echo
			echo 'docker-entrypoint init process complete; ready for start up.'
			echo
		fi
	fi

	if [ "$(id -u)" = '0' ]; then
		exec gosu nobody "$@"
	else
		exec "$@"
	fi
}

if ! _is_sourced; then
	_main "$@"
fi
