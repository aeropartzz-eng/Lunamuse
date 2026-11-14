FROM python:3.12-slim

WORKDIR /app

# Dependências de sistema mínimas (curl para o healthcheck do compose)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Usuário não-root
RUN useradd -m cbi && chown -R cbi:cbi /app
USER cbi

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
