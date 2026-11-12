FROM python:3.12-slim

WORKDIR /app

# 依赖单独一层，改代码不必重装依赖
COPY system/requirements.txt ./system/requirements.txt
RUN pip install --no-cache-dir -r system/requirements.txt

# 只复制运行必需内容（详见 .dockerignore）
COPY api_server.py ./
COPY system/ ./system/

RUN mkdir -p 待识别发票 已归档发票 识别失败待处理 重复发票记录 X-处理中临时

ENV INVOICE_HOST=0.0.0.0 \
    INVOICE_PORT=5000 \
    PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["python", "api_server.py"]
