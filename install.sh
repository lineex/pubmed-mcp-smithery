#!/bin/bash

echo "Installing PubMed Enhanced MCP Server..."

# Check for Python
if command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo "Error: Python is not installed. Please install Python 3.6 or higher."
    exit 1
fi

# Check Python version
version=$($PYTHON -c 'import sys; print(sys.version_info.major, sys.version_info.minor)')
read -r major minor <<< "$version"

if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 6 ]); then
    echo "Error: Python 3.6 or higher is required. You have Python $major.$minor."
    exit 1
fi

# Create a virtual environment
echo "Creating virtual environment..."
$PYTHON -m venv venv

# Activate the virtual environment
if [ -d "venv/bin" ]; then
    source venv/bin/activate
else
    source venv/Scripts/activate
fi

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install fastmcp requests

echo "Installation complete!"
echo "To run the server, use: python pubmed_enhanced_mcp_server.py"
echo "For more information, see the README.md and USER_GUIDE.md files."