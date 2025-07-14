# Weather Data Platform

A comprehensive weather data analysis platform featuring an ETL pipeline for CSV data ingestion and an interactive Streamlit dashboard for visualization and forecasting.

## Features

- **PostgreSQL Database**: Stores weather data with optimized schema and indexes
- **ETL Pipeline**: Automated CSV file loading into PostgreSQL
- **Multi-page Dashboard**: Interactive Streamlit application with 5 analysis pages
- **Data Visualization**: Rich charts and heatmaps using Plotly
- **Forecasting**: Weather predictions using Facebook Prophet
- **Data Quality Monitoring**: Comprehensive data quality checks and reports

## Architecture

```
weather-data-platform/
├── postgres/
│   ├── Dockerfile
│   └── init.sql
├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   ├── etl/
│   │   ├── __init__.py
│   │   └── load_csv_to_pg.py
│   └── streamlit_app/
│       ├── __init__.py
│       ├── main.py
│       ├── utils.py
│       └── pages/
│           ├── 01_Overview.py
│           ├── 02_Trends.py
│           ├── 03_Heatmap.py
│           ├── 04_DataQuality.py
│           └── 05_Forecast.py
├── data/
│   └── (CSV files to be loaded)
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd weather-data-platform
   ```

2. **Set up environment variables**
   ```bash
   cp app/.env.example app/.env
   # Edit app/.env with your configuration
   ```

3. **Start the services**
   ```bash
   docker-compose up -d
   ```

4. **Access the dashboard**
   - Open http://localhost:8501 in your browser

5. **Load data**
   - Place CSV files in the `data/` directory
   - Run the ETL pipeline:
     ```bash
     docker-compose exec app python etl/load_csv_to_pg.py
     ```

## Data Format

CSV files should contain the following columns:
- `timestamp`: Date and time of observation (ISO format)
- `temperature`: Temperature in Celsius
- `humidity`: Relative humidity percentage (0-100)
- `pressure`: Atmospheric pressure in hPa
- `wind_speed`: Wind speed in m/s
- `wind_direction`: Wind direction in degrees (0-360)
- `precipitation`: Precipitation in mm
- `visibility`: Visibility in km
- `station_id`: Weather station identifier

## Dashboard Pages

### 1. Overview
- Key metrics and statistics
- Recent weather data
- Temperature and humidity trends
- Parameter distributions

### 2. Trends
- Time series analysis with multiple aggregation levels
- Moving averages
- Trend decomposition
- Multi-parameter comparisons

### 3. Heatmap
- Station vs Time visualization
- Hour vs Day patterns
- Month vs Year analysis
- Seasonal insights

### 4. Data Quality
- Completeness metrics
- Missing data analysis
- Validity checks
- Time series continuity
- Quality report generation

### 5. Forecast
- Prophet-based weather predictions
- Confidence intervals
- Model performance metrics
- Forecast components analysis

## Development

### Using Docker

```bash
# Build images
docker-compose build

# Start services
docker-compose up

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Local Development

1. **Install Python 3.12**

2. **Install dependencies**
   ```bash
   pip install -r app/requirements.txt
   ```

3. **Set up PostgreSQL**
   - Create database and user
   - Run `postgres/init.sql`

4. **Run Streamlit**
   ```bash
   streamlit run app/streamlit_app/main.py
   ```

## Configuration

Edit `app/.env` to configure:
- Database connection parameters
- Data directory path
- Application settings

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License.