#Using official python image
FROM python:3.9

#Update package list and install need packages 
RUN apt-get update && \
    apt-get install -y libgl1 tesseract-ocr libtesseract-dev libleptonica-dev tesseract-ocr-eng && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
    
#Set the timezone 
ENV TZ=America/New_York

#Set working dir    
WORKDIR /app

#copy the current dir contents into container
COPY . /app

#Install any extra neeeded packages using requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

#Expose port 8080
EXPOSE 8080

#Define environment variable  
ENV FLASK_APP=app.py

#Run app with gunicorn with 4 workers and increase timeout 
CMD ["gunicorn", "app:app", "-w", "4", "-t", "120", "-b", "0.0.0.0:8080"]
