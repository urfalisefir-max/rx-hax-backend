FROM python:3.10-slim

# Sistem seviyesinde Tesseract OCR ve kütüphanelerini kur
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python bağımlılıklarını kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalarını kopyala
COPY . .

# Uygulamayı başlat
CMD ["python", "app.py"]
