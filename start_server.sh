#!/bin/bash

# 確保 requests 和 fastmcp 已安裝
pip install fastmcp requests

# 運行 MCP 服務器
python pubmed_enhanced_mcp_server.py
