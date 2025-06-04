FROM python:alpine3.11
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
ENV FLASK_APP=app.py
ENV FLASK_ENV=development
EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0"]