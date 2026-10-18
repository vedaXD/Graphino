# Dockerfile for Bulwark DeFi (Next.js 16 + Python 3.11 + FalkorDB connector)
FROM node:20-bookworm-slim

# Install system dependencies and Python 3.11
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set up Python virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Node dependencies in Frontend
COPY Frontend/package*.json ./Frontend/
WORKDIR /app/Frontend
RUN npm install

# Copy application source code
WORKDIR /app
COPY . .

# Build Next.js application
WORKDIR /app/Frontend
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
RUN npm run build

# Configure startup environment
WORKDIR /app
RUN chmod +x /app/start.sh

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["/app/start.sh"]
