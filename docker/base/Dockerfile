FROM python:3.13.9
WORKDIR /app
LABEL authors="antonkuzmn1"

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/* && \
    pip install poetry
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction --no-ansi

ENTRYPOINT ["sleep", "3600"]