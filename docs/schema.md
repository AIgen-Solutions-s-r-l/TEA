# Weather Data Platform - Database Schema

## Overview
The Weather Data Platform uses PostgreSQL to store weather observations from multiple stations. The schema has been designed to capture all available data from the source CSV files.

## Tables

### weather_raw
The main table storing all weather observations.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| timestamp | TIMESTAMP | Date and time of observation |
| latitude | DECIMAL(10,8) | Station latitude coordinate |
| longitude | DECIMAL(11,8) | Station longitude coordinate |
| temperature | DECIMAL(5,2) | Temperature in Celsius |
| humidity | DECIMAL(5,2) | Relative humidity percentage |
| pressure | DECIMAL(7,2) | Atmospheric pressure in hPa (not available in current data) |
| wind_speed | DECIMAL(5,2) | Wind speed in m/s |
| wind_direction | DECIMAL(10,2) | Wind direction in degrees |
| precipitation | DECIMAL(5,2) | Precipitation in mm |
| precipitation_count | INTEGER | Precipitation event count (available for station 263) |
| visibility | DECIMAL(5,2) | Visibility in km (not available in current data) |
| radiation | DECIMAL(10,2) | Solar radiation in W/m² |
| station_id | VARCHAR(50) | Weather station identifier |
| loaded_at | TIMESTAMP | When the record was loaded into the database |

### Indexes
- `idx_weather_timestamp`: Index on timestamp for time-based queries
- `idx_weather_station`: Index on station_id for station filtering
- `idx_weather_timestamp_station`: Composite index for efficient time+station queries
- `idx_weather_location`: Spatial index on latitude/longitude for geographic queries

## Views

### weather_daily
Aggregated daily statistics per station.

| Column | Type | Description |
|--------|------|-------------|
| date | DATE | Date of aggregation |
| station_id | VARCHAR(50) | Weather station identifier |
| avg_temperature | NUMERIC | Average temperature for the day |
| min_temperature | NUMERIC | Minimum temperature for the day |
| max_temperature | NUMERIC | Maximum temperature for the day |
| avg_humidity | NUMERIC | Average humidity for the day |
| avg_pressure | NUMERIC | Average pressure for the day |
| avg_wind_speed | NUMERIC | Average wind speed for the day |
| avg_wind_direction | NUMERIC | Average wind direction for the day |
| avg_radiation | NUMERIC | Average solar radiation for the day |
| total_precipitation | NUMERIC | Total precipitation for the day |
| total_precipitation_count | NUMERIC | Total precipitation events for the day |
| avg_latitude | NUMERIC | Average latitude (should be constant per station) |
| avg_longitude | NUMERIC | Average longitude (should be constant per station) |
| observation_count | INTEGER | Number of observations for the day |

## Data Sources

The ETL process handles multiple CSV formats:

### Standard Format (Stations 256, 259, 260, 262)
- Time
- latitude, longitude
- extT (temperature)
- rh (humidity)
- pluv (precipitation)
- radN (radiation)
- wdir_ana (wind direction)
- wsp_ana (wind speed)

### Italian Format (Station 263)
- Time
- latitude, longitude
- T aria (°C) → temperature
- Umidità aria (%) → humidity
- pioggia (count) → precipitation_count
- pioggia (mm) → precipitation
- radiazione globale(W/m2) → radiation
- direzione vento (gradi) → wind_direction
- velocità vento (m/sec) → wind_speed

## Notes
- Some sensors report NaN values for wind measurements, indicating sensor issues
- Pressure and visibility columns exist in the schema but are not populated by current data sources
- Station 263 provides additional precipitation count data not available from other stations
- All timestamps are stored in UTC