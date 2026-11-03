# ECO-GALLO UAA · Dockerfile Oficial
# Contenedor para empaquetado y despliegue del proyecto
FROM python:3.11-slim

LABEL maintainer="ECO-GALLO UAA" \
      description="Marketplace universitario de economía circular (UAA)"

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar e instalar dependencias de Python primero (optimización de capas de caché)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copiar el código de la aplicación
COPY . .

# Asegurar directorios de datos requeridos
RUN mkdir -p data/uploads data/backups data/private/verificaciones

# Exponer puerto HTTP estándar de la aplicación
EXPOSE 8080

# Variables de entorno
ENV PORT=8080 \
    ECOGALLO_DATA=/app/data \
    PYTHONUNBUFFERED=1

# Comando de arranque del servicio
CMD ["python", "run_dev.py"]
