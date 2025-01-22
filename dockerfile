# Use official Python image as a base
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app

# Install required dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables (optional, for debugging purposes)
ENV FIREBASE_CREDENTIALS_PATH=./emotibit-32581-c99f09a8fb15.json
ENV FIREBASE_DATABASE_URL=https://emotibit-32581-default-rtdb.asia-southeast1.firebasedatabase.app/

# Run the application
CMD ["python", "main.py"]
