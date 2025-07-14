FROM postgres:16-alpine

# Copy initialization scripts
COPY init.sql /docker-entrypoint-initdb.d/

# Set default environment variables
ENV POSTGRES_DB=weather_db
ENV POSTGRES_USER=weather_user
ENV POSTGRES_PASSWORD=weather_password