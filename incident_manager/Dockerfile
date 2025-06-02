ARG PYTHON_VERSION=3.12.8-slim
ARG POETRY_VERSION=2.0.0

FROM python:$PYTHON_VERSION
ARG POETRY_VERSION


ENV \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1
    
# Set Poetry environment variables for non-interactive mode, virtual environments in project, auto creation, and cache directory
ENV \
    POETRY_VERSION=$POETRY_VERSION \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache


# Install Poetry package manager
RUN pip install poetry==$POETRY_VERSION --no-cache-dir

# Set the working directory inside the container
WORKDIR /app

COPY pyproject.toml poetry.lock ./

# Install project dependencies using Poetry
RUN poetry install --no-root --only main

# Copy the application code into the container
COPY . ./

# Install the application dependencies again to ensure everything is in place
RUN poetry install --only main

# Define the default command to run the application
CMD ["poetry", "run",  "python", "incident_manager/main.py"]

EXPOSE 8082