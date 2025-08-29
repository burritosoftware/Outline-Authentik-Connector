#use a lightweight image
FROM python:alpine

WORKDIR /app

#copy and install requirements
COPY ./requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

#disable buffering
ENV PYTHONUNBUFFERED=1

#copy application code
COPY ./src .

#start with uvicorn
CMD ["uvicorn", "connect:app", "--host", "0.0.0.0", "--port", "80"]
