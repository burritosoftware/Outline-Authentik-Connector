#use a lightweight image
FROM python:3.13-alpine

WORKDIR /app

#copy and install requirements
COPY ./requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

#disable buffering
ENV PYTHONUNBUFFERED=1

#copy application code
COPY ./src .

#define environment variables
ENV AUTHENTIK_URL=
ENV AUTHENTIK_TOKEN=
ENV OUTLINE_URL=
ENV OUTLINE_TOKEN=
ENV OUTLINE_WEBHOOK_SECRET=
ENV AUTO_CREATE_GROUPS=False
ENV SYNC_GROUP_REGEX=
ENV DEBUG=False

#expose port 80
EXPOSE 80

#start with uvicorn
CMD ["uvicorn", "connect:app", "--host", "0.0.0.0", "--port", "80"]
