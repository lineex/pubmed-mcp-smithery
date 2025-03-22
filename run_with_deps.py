#!/usr/bin/env python
import sys
import subprocess
import os

# 當前腳本所在目錄
script_dir = os.path.dirname(os.path.abspath(__file__))

# 嘗試安裝依賴
try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "fastmcp"])
    print("Dependencies installed successfully", file=sys.stderr)
except Exception as e:
    print(f"Failed to install dependencies: {str(e)}", file=sys.stderr)
    sys.exit(1)

# 運行 MCP 服務器
try:
    server_path = os.path.join(script_dir, "pubmed_enhanced_mcp_server.py")
    subprocess.check_call([sys.executable, server_path])
except Exception as e:
    print(f"Failed to run server: {str(e)}", file=sys.stderr)
    sys.exit(1)
