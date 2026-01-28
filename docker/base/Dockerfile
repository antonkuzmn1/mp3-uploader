FROM python:3.14
WORKDIR /app
LABEL authors="antonkuzmn1"

RUN apt-get update && \
    apt-get install -y ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

RUN curl -sSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv && \
    ln -s /root/.local/bin/uvx /usr/local/bin/uvx

COPY pyproject.toml uv.lock ./

RUN uv install

ENTRYPOINT ["sleep", "3600"]