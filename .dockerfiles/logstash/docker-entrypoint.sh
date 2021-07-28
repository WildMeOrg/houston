#!/bin/bash -e

# Map environment variables to entries in logstash.yml.
# Note that this will mutate logstash.yml in place if any such settings are found.
# This may be undesirable, especially if logstash.yml is bind-mounted from the
# host system.
env2yaml /usr/share/logstash/config/logstash.yml

export LS_JAVA_OPTS="-Dls.cgroup.cpuacct.path.override=/ -Dls.cgroup.cpu.path.override=/ $LS_JAVA_OPTS"

export POSTGRES_DRIVER_VERSION="42.2.19"

if [ ! -f "/usr/share/logstash/logstash-core/lib/jars/postgresql-${POSTGRES_DRIVER_VERSION}.jar" ]; then
    echo "Installing JDBC Postgres Driver..."
    curl -s -o "/usr/share/logstash/logstash-core/lib/jars/postgresql-${POSTGRES_DRIVER_VERSION}.jar" "https://jdbc.postgresql.org/download/postgresql-${POSTGRES_DRIVER_VERSION}.jar"
fi

if [[ -z $1 ]] || [[ ${1:0:1} == '-' ]] ; then
  exec logstash "$@"
else
  exec "$@"
fi
