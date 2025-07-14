-- Migration to fix wind_direction integer overflow issue
-- Changes wind_direction from INTEGER to DECIMAL to handle any numeric value

-- First, alter the column type
ALTER TABLE weather_raw 
ALTER COLUMN wind_direction TYPE DECIMAL(10,2);

-- Update the view to ensure it still works
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
    SUM(precipitation) as total_precipitation,
    COUNT(*) as observation_count
FROM weather_raw
GROUP BY DATE(timestamp), station_id;