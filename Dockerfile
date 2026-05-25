# Pinned to a specific digest for supply-chain integrity.
# To upgrade: bump the tag, run `docker pull python:3.13-alpine`, then
# `docker inspect --format='{{index .RepoDigests 0}}' python:3.13-alpine`
# and replace the sha256 below.
FROM python:3.13-alpine@sha256:420cd0bf0f3998275875e02ecd5808168cf0843cbb4d3c536432f729247b2acc

WORKDIR /app

#copy and install requirements
COPY ./requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

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

# wget is provided by busybox in alpine; verified present in python:3.13-alpine.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:80/ || exit 1

#drop root before runtime
RUN adduser -D -u 10001 app
USER app

#start with uvicorn
CMD ["uvicorn", "connect:app", "--host", "0.0.0.0", "--port", "80"]
