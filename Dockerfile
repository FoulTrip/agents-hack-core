# --- STAGE 1: Builder ---
FROM python:3.11-slim AS builder

# Evitar la creación de archivos .pyc y asegurar que los logs se emitan inmediatamente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependencias de compilación
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias de Python en un directorio local para copiar al runtime
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copiar el esquema de Prisma antes para generar el cliente
COPY prisma ./prisma

# Generar cliente de Prisma para Python
# Esto crea los archivos necesarios en la carpeta prisma/
RUN PYTHONPATH=/install/lib/python3.11/site-packages /install/bin/prisma generate --schema=./prisma/schema.prisma

# --- STAGE 2: Runtime ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV APP_HOME=/app

# Instalar tini para manejo correcto de señales de terminación (evita procesos zombie)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR $APP_HOME

# Crear un usuario no-root para seguridad
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copiar las librerías instaladas desde el builder
COPY --from=builder /install /usr/local

# Copiar el código de la aplicación
COPY . .

# Asegurar permisos correctos para el usuario no-root
RUN chown -R appuser:appuser $APP_HOME

# Cambiar al usuario de la aplicación
USER appuser

# Exponer el puerto configurado (Cloud Run inyectará su propio puerto, pero 8080 es el estándar)
EXPOSE 8080

# Usar tini como entrypoint para manejar señales (SIGTERM, SIGINT) correctamente
ENTRYPOINT ["/usr/bin/tini", "--"]

# Comando para iniciar la aplicación
# Usamos workers=1 ya que es una app stateful con WebSockets y Pipeline agents que consumen mucha CPU/RAM
# En Cloud Run se recomienda escalar por instancias, no por workers internos.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
