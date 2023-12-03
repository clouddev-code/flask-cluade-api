FROM python:3.10

WORKDIR /app

COPY . .

# requirements.txt 
RUN pip install -r requirements.txt

EXPOSE 8000

# 実行コマンド指定
ENTRYPOINT ["gunicorn", "-w", "2", "-b", "0.0.0.0", "src.app:app"]