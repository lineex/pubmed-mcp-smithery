#!/bin/bash

# Activate the virtual environment if it exists
if [ -d "venv/bin" ]; then
    source venv/bin/activate
elif [ -d "venv/Scripts" ]; then
    source venv/Scripts/activate
else
    echo "Virtual environment not found. Please run ./install.sh first."
    exit 1
fi

# Run the MCP server
python pubmed_enhanced_mcp_server.py
