FROM python:3.11-slim

WORKDIR /app

# 使用腾讯云内网镜像源，提升云托管构建速度与稳定性
RUN pip config set global.index-url http://mirrors.cloud.tencent.com/pypi/simple \
    && pip config set global.trusted-host mirrors.cloud.tencent.com

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 数据目录（SQLite 持久化挂载点；需在云托管挂载文件存储到 /data 才能持久化）
RUN mkdir -p /data
ENV DB_DIR=/data

# 端口必须与云托管「服务设置」-「监听端口」一致（Flask 模板默认 80）
EXPOSE 80

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
