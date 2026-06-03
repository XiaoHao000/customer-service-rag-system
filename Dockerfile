FROM python:3.11-slim

WORKDIR /app

# 系统依赖（OpenCV / PyMuPDF / torch / mysql-client 的运行时库）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖层（利用 Docker 缓存）—— torch 用 CPU 版本减小镜像体积
COPY requirements-docker.txt .
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-docker.txt

# 复制项目
COPY . .

# 入口脚本
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8003

ENTRYPOINT ["/docker-entrypoint.sh"]
