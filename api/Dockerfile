FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim

RUN useradd -m user

WORKDIR /app

COPY --from=builder /root/.local /home/user/.local
COPY . /app

COPY wait-for-it.sh /usr/local/bin/wait-for-it.sh
RUN chmod +x /usr/local/bin/wait-for-it.sh

RUN chown -R user:user /app /home/user/.local

USER user

ENV PATH=/home/user/.local/bin:$PATH

EXPOSE 8000

CMD ["sh", "-c", "/usr/local/bin/wait-for-it.sh db:5432 -- alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]