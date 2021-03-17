#!/usr/bin/env bash
set -Eueo pipefail

HERE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_GITLAB_CFG="${DATA_ROOT}/.python-gitlab.cfg"
GITLAB_REMOTE_URI="${GITLAB_REMOTE_URI:-${GITLAB_PROTO:-https}://${GITLAB_HOST}:${GITLAB_PORT}}"

write_initial_config() {
    cat <<EOF > $PYTHON_GITLAB_CFG
[global]
default = local-admin

[local-admin]
url = ${GITLAB_REMOTE_URI}
private_token = $1
ssl_verify = false

EOF
}

gitlab() {
    exec gitlab -o json -c $PYTHON_GITLAB_CFG "$@"
}

_main() {
    # Wait for gitlab to come online... this takes awhile, so we give feedback
    while ! $(wait-for -t 10 "${GITLAB_HOST}:${GITLAB_PORT}"); do
        echo "Waiting for the GitLab instance to come online"
    done

    echo "Complete the wizard setup for gitlab & create a admin personal access token (PAT)"
    admin_pat="$(python3 ${HERE_DIR}/_set_up_gitlab.py "${GITLAB_REMOTE_URI}" --admin-password "${GITLAB_ADMIN_PASSWORD}")"

    echo "Write the python-gitlab configuration file to: ${PYTHON_GITLAB_CFG}"
    write_initial_config $admin_pat

    echo "Create the 'houston' user"
    user_resp_json=$(gitlab user create --username houston --name Houston --email dev@wildme.org --password 'development' --can-create-group true --skip-confirmation true)
    user_id=$(echo "$user_resp_json" | python -c 'import json, sys; d = json.load(sys.stdin); print(d["id"])')

    echo "Create a PAT for the 'houston' user"
    pat_resp_json=$(curl --silent --request POST --header "PRIVATE-TOKEN: ${admin_pat}" --data "name=houston-integration" --data "scopes[]=api" "${GITLAB_REMOTE_URI}/api/v4/users/${user_id}/personal_access_tokens")
    houston_pat=$(echo "$pat_resp_json" | python -c 'import json, sys; d = json.load(sys.stdin); print(d["token"])')

    echo "Append 'houston' user PAT info to the python-gitlab configuration file"
    cat <<EOF >> $PYTHON_GITLAB_CFG
[local-user]
url = ${GITLAB_REMOTE_URI}
private_token = $houston_pat
ssl_verify = false
EOF

    echo "Create the 'test' group"
    group_resp_json=$(gitlab -g local-user group create --name TEST --path test)

    echo "Write 'houston' PAT to ${HOUSTON_DOTENV}"
    dotenv -f ${HOUSTON_DOTENV} set GITLAB_REMOTE_LOGIN_PAT "${houston_pat}"

    # Fix permissions on files
    chmod 644 ${HOUSTON_DOTENV} ${PYTHON_GITLAB_CFG}

    echo "GitLab setup complete"
}

_main
