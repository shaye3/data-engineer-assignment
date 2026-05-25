FROM python:3.12-slim
WORKDIR /app
COPY generator.py .
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "python generator.py --output-dir /input --rate ${RATE:-2} --size ${SIZE:-small} --sources ${SOURCES:-10}"]
