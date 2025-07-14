import streamlit as st
import pandas as pd
from utils import get_db_connection, load_data

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
    conn = get_db_connection()
    
    # Get record count
    with col1:
        query = "SELECT COUNT(*) FROM weather_raw"
        result = pd.read_sql(query, conn)
        record_count = result.iloc[0, 0]
        st.metric("Total Records", f"{record_count:,}")
    
    # Get station count
    with col2:
        query = "SELECT COUNT(DISTINCT station_id) FROM weather_raw"
        result = pd.read_sql(query, conn)
        station_count = result.iloc[0, 0]
        st.metric("Weather Stations", station_count)
    
    # Get date range
    with col3:
        query = """
        SELECT MIN(timestamp) as min_date, MAX(timestamp) as max_date 
        FROM weather_raw
        """
        result = pd.read_sql(query, conn)
        if not result.empty and result.iloc[0]['min_date'] is not None:
            min_date = pd.to_datetime(result.iloc[0]['min_date']).strftime('%Y-%m-%d')
            max_date = pd.to_datetime(result.iloc[0]['max_date']).strftime('%Y-%m-%d')
            st.metric("Date Range", f"{min_date} to {max_date}")
        else:
            st.metric("Date Range", "No data")
    
    conn.close()
    
    # Recent data preview
    st.markdown("### 📋 Recent Weather Data")
    df = load_data(limit=100)
    
    if not df.empty:
        # Format the dataframe for display
        display_df = df[['timestamp', 'station_id', 'temperature', 'humidity', 
                        'pressure', 'wind_speed', 'precipitation']].round(2)
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
    
    The platform expects CSV files with the following columns:
    - `timestamp`: Date and time of observation
    - `temperature`: Temperature in Celsius
    - `humidity`: Relative humidity percentage
    - `pressure`: Atmospheric pressure in hPa
    - `wind_speed`: Wind speed in m/s
    - `wind_direction`: Wind direction in degrees
    - `precipitation`: Precipitation in mm
    - `visibility`: Visibility in km
    - `station_id`: Weather station identifier
    """)

# Footer
st.markdown("---")
st.markdown("Weather Data Platform v1.0 | Built with Streamlit & PostgreSQL")