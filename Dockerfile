FROM python:3.9 as python_rust

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH \
    RUST_VERSION=1.60.0 \
    CLIENT_VERSION=0.0.3

RUN set -eux; \
    dpkgArch="$(dpkg --print-architecture)"; \
    case "${dpkgArch##*-}" in \
        amd64) rustArch='x86_64-unknown-linux-gnu'; rustupSha256='3dc5ef50861ee18657f9db2eeb7392f9c2a6c95c90ab41e45ab4ca71476b4338' ;; \
        armhf) rustArch='armv7-unknown-linux-gnueabihf'; rustupSha256='67777ac3bc17277102f2ed73fd5f14c51f4ca5963adadf7f174adf4ebc38747b' ;; \
        arm64) rustArch='aarch64-unknown-linux-gnu'; rustupSha256='32a1532f7cef072a667bac53f1a5542c99666c4071af0c9549795bbdb2069ec1' ;; \
        i386) rustArch='i686-unknown-linux-gnu'; rustupSha256='e50d1deb99048bc5782a0200aa33e4eea70747d49dffdc9d06812fd22a372515' ;; \
        *) echo >&2 "unsupported architecture: ${dpkgArch}"; exit 1 ;; \
    esac; \
    url="https://static.rust-lang.org/rustup/archive/1.24.3/${rustArch}/rustup-init"; \
    wget "$url"; \
    echo "${rustupSha256} *rustup-init" | sha256sum -c -; \
    chmod +x rustup-init; \
    ./rustup-init -y --no-modify-path --profile minimal --default-toolchain $RUST_VERSION --default-host ${rustArch}; \
    rm rustup-init; \
    chmod -R a+w $RUSTUP_HOME $CARGO_HOME; \
    rustup --version; \
    cargo --version; \
    rustc --version;

RUN apt-get update -y && apt-get install --yes --no-install-recommends patchelf cmake && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* 

RUN pip install maturin

RUN set -eux; \
    wget "https://github.com/tikv/client-py/archive/refs/tags/${CLIENT_VERSION}.tar.gz"; \
    tar -xzf 0.0.3.tar.gz; \
    cd client-py-${CLIENT_VERSION}; \
    maturin build; \
    cp target/wheels/tikv_client-${CLIENT_VERSION}-*.whl /


COPY . /nucliadb

WORKDIR /nucliadb

RUN set -eux; \
    cd nucliadb_node/binding; \
    maturin build

RUN cp /nucliadb/target/wheels/nucliadb_node*.whl /

# ---------------------------------------------------

FROM python:3.9

COPY --from=python_rust /tikv_client*.whl /
COPY --from=python_rust /nucliadb_node*.whl /

RUN pip install tikv_client-*.whl
RUN pip install nucliadb_node*.whl

RUN mkdir -p /usr/src/app

RUN pip install Cython==0.29.24 pybind11 gunicorn uvicorn uvloop

COPY nucliadb_utils/requirements.txt /usr/src/app/requirements-utils.txt
COPY nucliadb_utils/requirements-cache.txt /usr/src/app/requirements-cache.txt
COPY nucliadb_utils/requirements-storages.txt /usr/src/app/requirements-storages.txt
COPY nucliadb_utils/requirements-fastapi.txt /usr/src/app/requirements-fastapi.txt
COPY nucliadb_protos/python/requirements.txt /usr/src/app/requirements-protos.txt
COPY nucliadb_models/requirements.txt /usr/src/app/requirements-models.txt
COPY nucliadb_ingest/requirements.txt /usr/src/app/requirements-ingest.txt
COPY nucliadb_search/requirements.txt /usr/src/app/requirements-search.txt
COPY nucliadb_writer/requirements.txt /usr/src/app/requirements-writer.txt
COPY nucliadb_reader/requirements.txt /usr/src/app/requirements-reader.txt
COPY nucliadb_one/requirements.txt /usr/src/app/requirements-one.txt
COPY nucliadb_train/requirements.txt /usr/src/app/requirements-train.txt
COPY nucliadb_telemetry/requirements.txt /usr/src/app/requirements-telemetry.txt

RUN set -eux; \
    pip install --no-cache-dir \
    -r /usr/src/app/requirements-utils.txt \
    -r /usr/src/app/requirements-storages.txt \
    -r /usr/src/app/requirements-fastapi.txt \
    -r /usr/src/app/requirements-cache.txt \
    -r /usr/src/app/requirements-telemetry.txt \
    -r /usr/src/app/requirements-protos.txt \
    -r /usr/src/app/requirements-models.txt \
    -r /usr/src/app/requirements-ingest.txt \
    -r /usr/src/app/requirements-writer.txt \
    -r /usr/src/app/requirements-reader.txt \
    -r /usr/src/app/requirements-search.txt \
    -r /usr/src/app/requirements-one.txt \
    -r /usr/src/app/requirements-train.txt

# Copy source code
COPY nucliadb_utils /usr/src/app/nucliadb_utils
COPY nucliadb_telemetry /usr/src/app/nucliadb_telemetry
COPY nucliadb_protos /usr/src/app/nucliadb_protos
COPY nucliadb_models /usr/src/app/nucliadb_models
COPY nucliadb_ingest /usr/src/app/nucliadb_ingest
COPY nucliadb_search /usr/src/app/nucliadb_search
COPY nucliadb_writer /usr/src/app/nucliadb_writer
COPY nucliadb_reader /usr/src/app/nucliadb_reader
COPY nucliadb_one /usr/src/app/nucliadb_one
COPY nucliadb_train /usr/src/app/nucliadb_train
COPY nucliadb /usr/src/app/nucliadb

WORKDIR /usr/src/app

# Install all dependendencies on packages on the nucliadb repo
# and finally the main component.
RUN pip install -r nucliadb/requirements-sources.txt
RUN pip install --no-deps -e /usr/src/app/nucliadb

ENV NUA_ZONE=europe-1
ENV NUA_API_KEY=
ENV NUCLIA_PUBLIC_URL=https://{zone}.nuclia.cloud

# HTTP
EXPOSE 8080/tcp
# GRPC
EXPOSE 8030/tcp
# GRPC - TRAIN
EXPOSE 8031/tcp

CMD ["nucliadb"]