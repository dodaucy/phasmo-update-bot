# syntax=docker/dockerfile:1

FROM debian:stable-slim

# Install python and curl
RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-pip python3-venv curl
RUN apt-get clean
RUN rm -rf /var/lib/apt/lists/*

# Install pdm
RUN curl -sSL https://pdm-project.org/install-pdm.py | python3 -
ENV PDM_CHECK_UPDATE=false

# Create app directory
RUN mkdir /app
WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN /root/.local/bin/pdm install

# Copy files
COPY src/ .

# Python support
ENV PYTHONUNBUFFERED=true

# Start app
CMD ["/root/.local/bin/pdm", "run", "main.py"]
