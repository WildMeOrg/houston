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
        # nodejs \
 && rm -rf /var/lib/apt/lists/*

COPY . /code

WORKDIR /code

RUN set -ex \
 && pip install -e . \
 && invoke app.dependencies.install \
 #: Install developer tools
 && pip install utool ipython \
 #: Remove pip download cache
 && rm -rf ~/.cache/pip

USER nobody
EXPOSE 5000
ENV FLASK_CONFIG production

CMD [ "invoke", "app.run" ]
