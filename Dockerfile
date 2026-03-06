FROM python:3.12.8-bookworm
LABEL authors="Eko Indarto"

ARG BUILD_DATE
ENV BUILD_DATE=$BUILD_DATE


# Combine apt-get commands to reduce layers
RUN apt-get update -y && \
    apt-get upgrade -y && \
    apt-get dist-upgrade -y && \
    apt-get install -y --no-install-recommends git curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -ms /bin/bash akmi

ENV PYTHONPATH=/home/akmi/ocs/src
ENV BASE_DIR=/home/akmi/ocs

WORKDIR ${BASE_DIR}


# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the application into the container.


# Create and activate virtual environment
ENV APP_NAME="ost-clarin-skg"
ENV PATH="/home/akmi/ocs/.venv/bin:$PATH"
# Copy the application into the container.
COPY src ./src
#Temporary, will be removed later
COPY conf ./conf
COPY pyproject.toml .
COPY README.md .
COPY uv.lock .


RUN uv venv .venv
# Install dependencies

RUN uv sync --frozen --no-cache && chown -R akmi:akmi ${BASE_DIR}
USER akmi
RUN mkdir logs
# Run the application.
CMD ["python", "-m", "src.ost_clairin_skg.main"]

#CMD ["tail", "-f", "/dev/null"]