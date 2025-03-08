FROM python:3.9

RUN apt-get update && \
    apt-get install -y libgl1 tesseract-ocr libtesseract-dev libleptonica-dev tesseract-ocr-eng && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

ENV FLASK_APP=app.py

CMD ["gunicorn", "app:app", "-w", "4", "-t", "120", "-b", "0.0.0.0:8080"]