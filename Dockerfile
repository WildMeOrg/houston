FROM python:3.7

RUN apt update \
 # && curl -sL https://deb.nodesource.com/setup_14.x | bash - \
 && apt update \
 && apt upgrade -y \
 && apt install -y \
        # Build
        build-essential \
        musl-dev \
        gcc \
        libffi-dev \
        # Python 3
        python3-dev \
        # Convenience
        htop \
        tmux \
        vim \
        git \
        # Magic with python-magic (MIME-type parser)
        libmagic1 \
        #: tool to setuid+setgid+setgroups+exec at execution time
        gosu \
        #: required by wait-for
        netcat \
        #: required for downloading 'wait-for'
        curl \
 && rm -rf /var/lib/apt/lists/*

# Install wait-for
RUN set -x \
    && curl -s https://raw.githubusercontent.com/eficode/wait-for/v2.0.0/wait-for > /usr/local/bin/wait-for \
    && chmod a+x /usr/local/bin/wait-for \
    # test it works
    && wait-for google.com:80 -- echo "success"

COPY . /code

WORKDIR /code

RUN set -ex \
 && pip install -e . \
 && invoke app.dependencies.install \
 #: Install developer tools
 && pip install utool ipython \
 #: Remove pip download cache
 && rm -rf ~/.cache/pip

EXPOSE 5000
ENV FLASK_CONFIG production

# Location to mount our data
ENV DATA_VOLUME /data
# Location the data will be writen to
ENV DATA_ROOT ${DATA_VOLUME}/var
VOLUME [ "${DATA_VOLUME}" ]

COPY ./.dockerfiles/docker-entrypoint.sh /docker-entrypoint.sh

ENTRYPOINT [ "/docker-entrypoint.sh" ]
#: default command within the entrypoint
# CMD [ "invoke", "app.run" ]
