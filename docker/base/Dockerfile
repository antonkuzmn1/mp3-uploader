FROM python:3.14
WORKDIR /app
LABEL authors="antonkuzmn1"

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/* \

RUN pip install uv

COPY pyproject.toml uv.lock ./

RUN uv install

ENTRYPOINT ["sleep", "3600"]