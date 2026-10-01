FROM python:3.11-alpine

RUN apk add --no-cache \
    iproute2 \
    iputils \
    bind-tools

WORKDIR /app
COPY router.py .

CMD ["python3", "-u", "router.py"]
