import streamlit as st
import pandas as pd
import numpy as np
import psycopg2
from utils import get_db_connection, load_data, DB_CONFIG

# Page configuration
st.set_page_config(
    page_title="Weather Data Platform",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Main page content
st.title("🌤️ Weather Data Platform")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("Navigation")
    st.markdown("""
    This platform provides comprehensive weather data analysis and visualization.
    
    **Available Pages:**
    - 📊 **Overview**: Summary statistics and recent data
    - 📈 **Trends**: Time series analysis
    - 🗺️ **Heatmap**: Spatial visualization
    - 🔍 **Data Quality**: Data completeness and quality metrics
    - 🔮 **Forecast**: Weather predictions using Prophet
    """)
    
    # Add refresh button
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# Main content
col1, col2, col3 = st.columns(3)

# Load basic statistics
try:
    # Get record count
    with col1:
        conn = psycopg2.connect(**DB_CONFIG)
        query = "SELECT COUNT(*) FROM weather_raw"
        result = pd.read_sql(query, conn)
        record_count = result.iloc[0, 0]
        st.metric("Total Records", f"{record_count:,}")
        conn.close()
    
    # Get station count
    with col2:
        conn = psycopg2.connect(**DB_CONFIG)
        query = "SELECT COUNT(DISTINCT station_id) FROM weather_raw"
        result = pd.read_sql(query, conn)
        station_count = result.iloc[0, 0]
        st.metric("Weather Stations", station_count)
        conn.close()
    
    # Get date range
    with col3:
        conn = psycopg2.connect(**DB_CONFIG)
        query = """
        SELECT MIN(timestamp) as min_date, MAX(timestamp) as max_date 
        FROM weather_raw
        """
        result = pd.read_sql(query, conn)
        conn.close()
        
        if not result.empty and result.iloc[0]['min_date'] is not None:
            min_date = pd.to_datetime(result.iloc[0]['min_date']).strftime('%Y-%m-%d')
            max_date = pd.to_datetime(result.iloc[0]['max_date']).strftime('%Y-%m-%d')
            st.metric("Date Range", f"{min_date} to {max_date}")
        else:
            st.metric("Date Range", "No data")
    
    # Recent data preview
    st.markdown("### 📋 Recent Weather Data")
    
    # Show data availability summary
    conn = psycopg2.connect(**DB_CONFIG)
    availability_query = """
        SELECT 
            COUNT(CASE WHEN temperature IS NOT NULL THEN 1 END) as has_temperature,
            COUNT(CASE WHEN humidity IS NOT NULL THEN 1 END) as has_humidity,
            COUNT(CASE WHEN wind_speed IS NOT NULL AND wind_speed != 'NaN' THEN 1 END) as has_wind_speed,
            COUNT(CASE WHEN wind_direction IS NOT NULL AND wind_direction != 'NaN' THEN 1 END) as has_wind_direction,
            COUNT(CASE WHEN precipitation IS NOT NULL THEN 1 END) as has_precipitation,
            COUNT(CASE WHEN radiation IS NOT NULL THEN 1 END) as has_radiation,
            COUNT(*) as total_records
        FROM weather_raw
    """
    availability = pd.read_sql(availability_query, conn)
    conn.close()
    
    if not availability.empty:
        st.info(f"""
        **Data Coverage**: 
        Temperature: {availability['has_temperature'].iloc[0]:,} records | 
        Humidity: {availability['has_humidity'].iloc[0]:,} records | 
        Wind Speed: {availability['has_wind_speed'].iloc[0]:,} records | 
        Wind Direction: {availability['has_wind_direction'].iloc[0]:,} records |
        Precipitation: {availability['has_precipitation'].iloc[0]:,} records |
        Radiation: {availability['has_radiation'].iloc[0]:,} records
        """)
    
    df = load_data(limit=100)
    
    if not df.empty:
        # Format the dataframe for display
        # Select only columns that exist in the dataframe and have data
        display_columns = ['timestamp', 'station_id']
        # Only show columns that actually have data in the CSV files
        optional_columns = ['temperature', 'humidity', 'wind_speed', 'wind_direction', 'precipitation', 'radiation']
        
        # Add optional columns if they exist
        for col in optional_columns:
            if col in df.columns:
                display_columns.append(col)
        
        display_df = df[display_columns].copy()
        
        # Round numeric columns (but handle NaN properly)
        numeric_columns = display_df.select_dtypes(include=[np.float64, np.float32]).columns
        for col in numeric_columns:
            # Round only non-NaN values
            mask = display_df[col].notna() & (display_df[col] != float('inf')) & (display_df[col] != float('-inf'))
            display_df.loc[mask, col] = display_df.loc[mask, col].round(2)
        
        # Replace NaN and infinity with more readable text
        display_df = display_df.replace([np.inf, -np.inf, np.nan], '-')
        
        # Format timestamp
        if 'timestamp' in display_df.columns:
            display_df['timestamp'] = pd.to_datetime(display_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
        
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No weather data available. Please load some data using the ETL pipeline.")
    
except Exception as e:
    st.error(f"Error connecting to database: {e}")
    st.info("Please ensure the database is running and properly configured.")

# Instructions
with st.expander("📖 How to Use This Platform"):
    st.markdown("""
    ### Getting Started
    
    1. **Load Data**: Use the ETL pipeline to load CSV files from the `/data` directory
    2. **Navigate**: Use the sidebar to explore different analysis pages
    3. **Filter**: Most pages allow filtering by date range and station
    4. **Export**: Download visualizations and data as needed
    
    ### Data Format
    
    The platform processes CSV files with the following columns:
    - `Time`: Date and time of observation
    - `extT`: Temperature in Celsius
    - `rh`: Relative humidity percentage
    - `wsp_ana`: Wind speed in m/s
    - `wdir_ana`: Wind direction in degrees
    - `pluv`: Precipitation in mm
    - `radN`: Solar radiation
    - `latitude/longitude`: Station coordinates
    
    Note: Pressure and visibility data are not available in the current dataset.
    """)

# Footer
st.markdown("---")
st.markdown("Weather Data Platform v1.0 | Built with Streamlit & PostgreSQL")