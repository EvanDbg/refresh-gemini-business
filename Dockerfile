# Multi-stage Dockerfile for Gemini Business Cookie Refresh Tool
# Supports both amd64 and arm64 architectures
# Uses Xvfb to run browser in non-headless mode (required to bypass detection)

FROM mcr.microsoft.com/playwright/python:v1.49.1-noble AS base

# Set working directory
WORKDIR /app

# Set versions
ARG MIHOMO_VERSION=v1.19.19

# Install additional dependencies including Xvfb
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    ca-certificates \
    gzip \
    xvfb \
    x11-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium --with-deps

# Download Mihomo based on architecture
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "amd64" ]; then \
        wget -O /tmp/mihomo.gz "https://github.com/MetaCubeX/mihomo/releases/download/${MIHOMO_VERSION}/mihomo-linux-amd64-${MIHOMO_VERSION}.gz" && \
        gzip -d /tmp/mihomo.gz && \
        mv /tmp/mihomo /usr/local/bin/mihomo && \
        chmod +x /usr/local/bin/mihomo; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        wget -O /tmp/mihomo.gz "https://github.com/MetaCubeX/mihomo/releases/download/${MIHOMO_VERSION}/mihomo-linux-arm64-${MIHOMO_VERSION}.gz" && \
        gzip -d /tmp/mihomo.gz && \
        mv /tmp/mihomo /usr/local/bin/mihomo && \
        chmod +x /usr/local/bin/mihomo; \
    fi

# Verify mihomo installation
RUN mihomo -v

# Download GeoIP database for Mihomo
RUN mkdir -p /root/.config/mihomo && \
    wget -O /root/.config/mihomo/Country.mmdb \
    "https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country.mmdb"

# Copy application code
COPY src/ ./src/
COPY extensions/ ./extensions/

# Copy config files
COPY .env.example .env
COPY local.yaml.example local.yaml.example

# Copy and setup entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create data and temp directories
RUN mkdir -p /data /tmp/gemini-browser-profile

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV CLASH_EXECUTABLE=/usr/local/bin/mihomo
ENV CLASH_CONFIG=/data/local.yaml
ENV INPUT_CSV_PATH=/data/result.csv
ENV OUTPUT_JSON_PATH=/data/accounts.json
ENV DISPLAY=:99

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:29090/ || exit 1

# Use entrypoint script that starts Xvfb
ENTRYPOINT ["/entrypoint.sh"]
