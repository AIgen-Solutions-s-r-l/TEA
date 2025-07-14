-- Migration to add all missing columns from CSV files
-- This ensures we capture ALL available data

-- Add latitude and longitude columns
ALTER TABLE weather_raw 
ADD COLUMN IF NOT EXISTS latitude DECIMAL(10,8),
ADD COLUMN IF NOT EXISTS longitude DECIMAL(11,8);

-- Add radiation column (if not already added)
ALTER TABLE weather_raw 
ADD COLUMN IF NOT EXISTS radiation DECIMAL(10,2);

-- Add precipitation_count column (from station 263)
ALTER TABLE weather_raw 
ADD COLUMN IF NOT EXISTS precipitation_count INTEGER;

-- Create indexes for geographic queries
CREATE INDEX IF NOT EXISTS idx_weather_location ON weather_raw(latitude, longitude);

-- Update the daily view to include new columns
DROP VIEW IF EXISTS weather_daily;

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