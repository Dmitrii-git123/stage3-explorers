FROM python:3.11-slim
WORKDIR /app
RUN pip install flask==2.3.3
COPY main.py .
EXPOSE 8000
CMD [python, main.py]
