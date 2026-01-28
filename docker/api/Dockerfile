FROM docker.antonkuzm.in/mp3-uploader/base:latest

COPY src/ ./src/
RUN rm -rf ./src/telegram

EXPOSE 8000

ENTRYPOINT ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]