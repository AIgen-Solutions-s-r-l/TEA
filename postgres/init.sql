-- Create weather_raw table
CREATE TABLE IF NOT EXISTS weather_raw (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    temperature DECIMAL(5,2),
    humidity DECIMAL(5,2),
    pressure DECIMAL(7,2),
    wind_speed DECIMAL(5,2),
    wind_direction INTEGER,
    precipitation DECIMAL(5,2),
    visibility DECIMAL(5,2),
    station_id VARCHAR(50),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX idx_weather_timestamp ON weather_raw(timestamp);
CREATE INDEX idx_weather_station ON weather_raw(station_id);
CREATE INDEX idx_weather_timestamp_station ON weather_raw(timestamp, station_id);

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
    SUM(precipitation) as total_precipitation,
    COUNT(*) as observation_count
FROM weather_raw
GROUP BY DATE(timestamp), station_id;