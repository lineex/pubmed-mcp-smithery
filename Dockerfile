FROM python:3.10-alpine

# 安装系统依赖项
RUN apk add --no-cache build-base \
    && apk add --no-cache libffi-dev openssl-dev

# 设置工作目录
WORKDIR /app

# 将当前目录内容复制到容器的 /app 目录
COPY . /app

# 升级 pip
RUN pip install --upgrade pip

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 运行 MCP 服务器
CMD ["python", "pubmed_enhanced_mcp_server.py"]
