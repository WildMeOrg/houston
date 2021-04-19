#!/usr/bin/env bash
set -Eeo pipefail

# A flag file used to indicate that the application's data has been initialized
INITIALIZED_FLAG_FILE="${DATA_ROOT}/.initialized"

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

# usage: docker_process_init_files [file [file [...]]]
#    ie: docker_process_init_files /init.d/*
# process initializer files, based on file extensions and permissions
docker_process_init_files() {
	local f
	for f; do
		case "$f" in
			*.sh)
				# https://github.com/docker-library/postgres/issues/450#issuecomment-393167936
				# https://github.com/docker-library/postgres/pull/452
				if [ -x "$f" ]; then
					echo "$0: running $f"
					"$f"
				else
					echo "$0: sourcing $f"
					. "$f"
				fi
				;;
			*.source-sh)
				# test -x "$f" on a volume mounted file causes `-x` to report
				# true if the file exist regardless of execution permissions
				echo "$0: sourcing $f"
				. "$f"
				;;
			*)        echo "$0: ignoring $f" ;;
		esac
		echo
	done
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
	if [ -f "${INITIALIZED_FLAG_FILE}" ]; then
		ALREADY_INITIALIZED='true'
	fi
}

# assume the container is in development-mode when the .git directory is present
_is_development_env() {
	[ -d /code/.git ]
}

set_up_development_mode() {
	pip install -e ".[testing]"
	# stamp the version.py file in the code
	python setup.py --version
	# setup the swagger-ui within the development code
	invoke dependencies.install-swagger-ui
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
		if [ _is_development_env ]; then
			set_up_development_mode
		fi
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

			if [ -d /docker-entrypoint-init.d ]; then
				docker_process_init_files /docker-entrypoint-init.d/*
			fi
			echo
			echo 'docker-entrypoint init process complete; ready for start up.'
			echo
			echo "initialized on $(date)" > ${INITIALIZED_FLAG_FILE}
		fi
	fi

	# Always process these initialization scripts
	if [ -d /docker-entrypoint-always-init.d ]; then
		docker_process_init_files /docker-entrypoint-always-init.d/*
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
