-- Create weather_raw table with all available columns from CSV files
CREATE TABLE IF NOT EXISTS weather_raw (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    temperature DECIMAL(5,2),
    humidity DECIMAL(5,2),
    pressure DECIMAL(7,2),
    wind_speed DECIMAL(5,2),
    wind_direction DECIMAL(10,2),
    precipitation DECIMAL(5,2),
    precipitation_count INTEGER,
    visibility DECIMAL(5,2),
    radiation DECIMAL(10,2),
    station_id VARCHAR(50),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX idx_weather_timestamp ON weather_raw(timestamp);
CREATE INDEX idx_weather_station ON weather_raw(station_id);
CREATE INDEX idx_weather_timestamp_station ON weather_raw(timestamp, station_id);
CREATE INDEX idx_weather_location ON weather_raw(latitude, longitude);

-- Create a view for daily aggregates
CREATE VIEW weather_daily AS
SELECT 
    DATE(timestamp) as date,
    station_id,
    AVG(temperature) as avg_temperature,
    MIN(temperature) as min_temperature,
    MAX(temperature) as max_temperature,
    AVG(humidity) as avg_humidity,
    AVG(pressure) as avg_pressure,
    AVG(wind_speed) as avg_wind_speed,
    AVG(wind_direction) as avg_wind_direction,
    AVG(radiation) as avg_radiation,
    SUM(precipitation) as total_precipitation,
    SUM(precipitation_count) as total_precipitation_count,
    AVG(latitude) as avg_latitude,
    AVG(longitude) as avg_longitude,
    COUNT(*) as observation_count
FROM weather_raw
GROUP BY DATE(timestamp), station_id;