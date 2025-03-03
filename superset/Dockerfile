FROM apache/superset

USER root

# Install system dependencies
RUN apt-get update && \
    apt-get install -y pkg-config default-libmysqlclient-dev build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install pymysql
RUN pip install pymysql mysqlclient

# Fix the tag creation issue by directly modifying the file
RUN sed -i 's/tag = Tag(name=escape(tag_name), type=type_)/tag = Tag(name=tag_name, type=type_)/' /app/superset/tags/models.py

# Add a comment to show the image was patched
LABEL maintainer="Custom patched Superset with tag creation fix"

# Switch back to superset user
USER superset
