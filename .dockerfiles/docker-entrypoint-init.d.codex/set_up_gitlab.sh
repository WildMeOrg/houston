#!/usr/bin/env bash
set -Eueo pipefail

HERE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_GITLAB_CFG="${DATA_ROOT}/.python-gitlab.cfg"
GIT_SSH_KEY_FILEPATH="${DATA_ROOT}/id_ssh_key"
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
    if [ "${GITLAB_REMOTE_URI:0:4}" != "http" ]; then
        echo "Not using gitlab, exit"
        exit
    fi

    if [ -n "${GITLAB_REMOTE_LOGIN_PAT:-}" ]; then
        echo "GITLAB_REMOTE_LOGIN_PAT already set, exit"
        exit
    fi

    # Wait for gitlab to come online... this takes awhile, so we give feedback
    while ! $(wait-for -t 10 "${GITLAB_HOST}:${GITLAB_PORT}"); do
        echo "Waiting for the GitLab instance to come online"
    done

    echo "Complete the wizard setup for gitlab & create a admin personal access token (PAT)"
    admin_pat="$(python3 ${HERE_DIR}/_set_up_gitlab.py "${GITLAB_REMOTE_URI}" --admin-password "${GITLAB_ADMIN_PASSWORD}")"

    echo "Write the python-gitlab configuration file to: ${PYTHON_GITLAB_CFG}"
    write_initial_config $admin_pat

    echo "Look for the 'houston' user"
    user_list_json=$(gitlab user list --username houston)
    if [ "$user_list_json" == "[]" ]; then
        echo "Create the 'houston' user"
        user_resp_json=$(gitlab user create --username houston --name Houston --email dev@wildme.org --password 'development' --can-create-group true --skip-confirmation true)
        user_id=$(echo "$user_resp_json" | python -c 'import json, sys; d = json.load(sys.stdin); print(d["id"])')
    else
        echo "User 'houston' already exists"
        user_id=$(echo "$user_list_json" | python -c 'import json, sys; d = json.load(sys.stdin); print(d[0]["id"])')
    fi

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

    group_resp_json=$(gitlab -g local-user group list --search test)
    if ! echo $group_resp_json | grep '"path": "test"'; then
        echo "Create the 'test' group"
        group_resp_json=$(gitlab -g local-user group create --name TEST --path test)
    fi

    echo "Write 'houston' PAT to ${HOUSTON_DOTENV}"
    dotenv -f ${HOUSTON_DOTENV} set GITLAB_REMOTE_LOGIN_PAT -- "${houston_pat}"

    echo "Create a SSH key pair for the 'houston' user"
    if [ -f "${GIT_SSH_KEY_FILEPATH}" ]; then
        echo "Found and removing existing SSH key pair"
        rm -f ${GIT_SSH_KEY_FILEPATH} ${GIT_SSH_KEY_FILEPATH}.pub
    fi
    ssh-keygen -t ecdsa -b 521 -C "Houston (${user_id})" -f "${GIT_SSH_KEY_FILEPATH}" -N ""
    echo "Send the 'houston' user's public ssh key to gitlab"
    resp=$(gitlab user-key create --user-id ${user_id} --title "Houston Application" --key "$(cat ${GIT_SSH_KEY_FILEPATH}.pub)")
    # See also https://docs.gitlab.com/ee/ssh/
    echo "Testing ssh connectivity"
    gitlab_host=$(python -c "import os; print(os.getenv('GITLAB_REMOTE_URI').strip('/').split('/')[-1])")
    # Test the SSH connection to the gitlab host
    # Note, `-o StrictHostKeyChecking=no` option forces the connection to be added to known_hosts
    ssh -i ${GIT_SSH_KEY_FILEPATH} -T "git@${gitlab_host}" -o StrictHostKeyChecking=no
    echo "Write 'houston' ssh key to ${HOUSTON_DOTENV}"
    dotenv -f ${HOUSTON_DOTENV} set GIT_SSH_KEY -- "$(cat ${GIT_SSH_KEY_FILEPATH})"

    # Fix permissions on files
    chmod 644 ${HOUSTON_DOTENV} ${PYTHON_GITLAB_CFG}

    echo "GitLab setup complete"
}

_main
