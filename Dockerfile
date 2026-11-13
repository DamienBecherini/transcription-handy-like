FROM python:3.12-slim-trixie

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY transcription/ transcription/

# Models downloaded on first start into this volume (Hugging Face cache), checked by sha256.
ENV HF_HOME=/models PYTHONUNBUFFERED=1
RUN useradd -u 1000 -m transcription && mkdir /models && chown transcription /models
USER transcription
VOLUME /models
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=120s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1
CMD ["uvicorn", "transcription.server:app", "--host", "0.0.0.0", "--port", "8000"]
