FROM python:3.11-slim

# Instalar dependencias del sistema (curl para poetry, ffmpeg para procesamiento de video)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Configurar variables de entorno de Poetry
ENV POETRY_VERSION=1.8.2 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1
ENV PATH="$POETRY_HOME/bin:$PATH"

# Instalar Poetry de forma oficial
RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

# Copiar archivos de dependencias primero para aprovechar el cache de Docker
COPY pyproject.toml poetry.lock ./

# Instalar dependencias de Python del proyecto
RUN poetry install --no-root --only main

# Copiar el resto del código fuente al contenedor
COPY . .

# Puerto interno que Caddy va a buscar
EXPOSE 8000

# Ejecutar la aplicación usando el entorno virtual de Poetry
CMD ["poetry", "run", "python", "main.py"]