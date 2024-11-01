FROM  nvidia/cuda:12.5.0-devel-ubuntu22.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg \
       python3.11 \
       python3.11-venv \
       wget \
    && rm -rf /var/lib/apt/lists/*  \
    && wget https://bootstrap.pypa.io/get-pip.py -O get-pip.py \
    && python3.11 get-pip.py \
    && rm get-pip.py

WORKDIR /app

COPY wait-for-it.sh /usr/local/bin/wait-for-it.sh
RUN chmod +x /usr/local/bin/wait-for-it.sh

COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

RUN useradd -m workeruser

COPY . /app

RUN chown -R workeruser:workeruser /app

USER workeruser
ENV PATH="/home/workeruser/.local/bin:${PATH}"

CMD ["sh", "-c", "/usr/local/bin/wait-for-it.sh rabbitmq:5672 -- /usr/local/bin/wait-for-it.sh rabbitmq:5672 -- python3.11 worker.py"]
