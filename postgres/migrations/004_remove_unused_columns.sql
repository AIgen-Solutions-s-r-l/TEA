-- Migration to remove columns that are not present in the source CSV files
-- This avoids confusion in the Data Quality page

-- First drop the view that depends on these columns
DROP VIEW IF EXISTS weather_daily;

-- Remove columns that don't exist in our data sources
ALTER TABLE weather_raw 
DROP COLUMN IF EXISTS pressure CASCADE,
DROP COLUMN IF EXISTS visibility CASCADE;

CREATE VIEW weather_daily AS
SELECT 
    DATE(timestamp) as date,
    station_id,
    AVG(temperature) as avg_temperature,
    MIN(temperature) as min_temperature,
    MAX(temperature) as max_temperature,
    AVG(humidity) as avg_humidity,
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

-- Add comment to document available vs unavailable data
COMMENT ON TABLE weather_raw IS 'Weather observations from CSV files. Note: pressure, visibility, and particle data are not available in the current data sources.';