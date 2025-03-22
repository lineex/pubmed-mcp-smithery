FROM python:3.10-alpine

# Install system dependencies
RUN apk add --no-cache build-base \
    && apk add --no-cache libffi-dev openssl-dev

# Set working directory
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Upgrade pip
RUN pip install --upgrade pip

# Install dependencies
RUN pip install --no-cache-dir fastmcp requests

# Run the MCP server
CMD ["python", "pubmed_enhanced_mcp_server.py"]