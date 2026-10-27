# Multi-stage Dockerfile for video-cut application
# Production-ready with minimal image size and security best practices

# ============================================================================
# Stage 1: Build dependencies
# ============================================================================
FROM python:3.12-slim-bookworm AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY pyproject.toml .

# Install packages to a virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip && \
    pip install hatchling && \
    pip install -e .

# ============================================================================
# Stage 2: Runtime image
# ============================================================================
FROM python:3.12-slim-bookworm AS runtime

# Labels for the image
LABEL maintainer="video-cut-team"
LABEL description="Video highlight extraction tool with user authentication"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_HOME=/app \
    APP_USER=appuser \
    APP_GROUP=appgroup

# Install runtime dependencies including FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r ${APP_GROUP} && \
    useradd -r -g ${APP_GROUP} -d ${APP_HOME} -s /sbin/nologin \
    -c "Application User" ${APP_USER}

# Set working directory
WORKDIR ${APP_HOME}

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY src/ ${APP_HOME}/src/
COPY start_server.py .
COPY AUTHENTICATION.md .

# Create necessary directories with proper permissions
RUN mkdir -p data output logs && \
    chown -R ${APP_USER}:${APP_GROUP} ${APP_HOME} && \
    chmod -R 755 ${APP_HOME}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8462/auth/me || exit 1

# Expose port
EXPOSE 8462

# Switch to non-root user
USER ${APP_USER}

# Default command
CMD ["python", "start_server.py"]
