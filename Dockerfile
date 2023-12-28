FROM python:3.11

RUN mkdir /app

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/.

ENTRYPOINT [ "python", "/app/main.py" ]