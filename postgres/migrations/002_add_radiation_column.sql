-- Add radiation column that exists in CSV files but was missing from schema
ALTER TABLE weather_raw 
ADD COLUMN IF NOT EXISTS radiation DECIMAL(10,2);

-- Update the daily view to include radiation
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
    COUNT(*) as observation_count
FROM weather_raw
GROUP BY DATE(timestamp), station_id;