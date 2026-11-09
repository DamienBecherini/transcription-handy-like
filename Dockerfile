FROM python:3.12-slim-trixie

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY transcription/ transcription/

# Modèles téléchargés au premier démarrage dans ce volume (cache Hugging Face), vérifiés par sha256.
ENV HF_HOME=/modeles PYTHONUNBUFFERED=1
RUN useradd -u 1000 -m transcription && mkdir /modeles && chown transcription /modeles
USER transcription
VOLUME /modeles
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=120s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1
CMD ["uvicorn", "transcription.serveur:app", "--host", "0.0.0.0", "--port", "8000"]
