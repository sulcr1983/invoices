FROM python:3.12-slim

WORKDIR /app

COPY system/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p 待识别发票 已归档发票 识别失败待处理 重复发票记录 X-处理中临时

EXPOSE 5000

CMD ["python", "system/api_server.py"]
