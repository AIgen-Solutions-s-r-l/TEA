import os
import psycopg2
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'weather_db'),
    'user': os.getenv('DB_USER', 'weather_user'),
    'password': os.getenv('DB_PASSWORD', 'weather_password')
}

@st.cache_resource
def get_db_connection():
    """Create and return a database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        raise

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data(start_date=None, end_date=None, station_id=None, limit=None):
    """Load weather data from database with optional filters"""
    conn = get_db_connection()
    
    query = "SELECT * FROM weather_raw WHERE 1=1"
    params = []
    
    if start_date:
        query += " AND timestamp >= %s"
        params.append(start_date)
    
    if end_date:
        query += " AND timestamp <= %s"
        params.append(end_date)
    
    if station_id:
        query += " AND station_id = %s"
        params.append(station_id)
    
    query += " ORDER BY timestamp DESC"
    
    if limit:
        query += f" LIMIT {limit}"
    
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    
    return df

@st.cache_data(ttl=300)
def get_stations():
    """Get list of available weather stations"""
    conn = get_db_connection()
    query = """
    SELECT DISTINCT station_id 
    FROM weather_raw 
    WHERE station_id IS NOT NULL 
    ORDER BY station_id
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    return df['station_id'].tolist()

@st.cache_data(ttl=300)
def get_date_range():
    """Get the available date range in the database"""
    conn = get_db_connection()
    query = """
    SELECT 
        MIN(timestamp) as min_date, 
        MAX(timestamp) as max_date 
    FROM weather_raw
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    if not df.empty and df.iloc[0]['min_date'] is not None:
        return pd.to_datetime(df.iloc[0]['min_date']), pd.to_datetime(df.iloc[0]['max_date'])
    else:
        return None, None

def create_date_filter():
    """Create date range filter widgets"""
    col1, col2 = st.columns(2)
    
    min_date, max_date = get_date_range()
    
    if min_date and max_date:
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=max_date - timedelta(days=7),
                min_value=min_date.date(),
                max_value=max_date.date()
            )
        
        with col2:
            end_date = st.date_input(
                "End Date",
                value=max_date.date(),
                min_value=min_date.date(),
                max_value=max_date.date()
            )
        
        return start_date, end_date
    else:
        st.warning("No data available in database")
        return None, None

def create_station_filter():
    """Create station selection widget"""
    stations = get_stations()
    
    if stations:
        station_id = st.selectbox(
            "Select Weather Station",
            options=['All Stations'] + stations
        )
        
        return None if station_id == 'All Stations' else station_id
    else:
        st.warning("No stations available")
        return None

@st.cache_data(ttl=300)
def get_summary_statistics(df, column):
    """Calculate summary statistics for a given column"""
    if column not in df.columns or df[column].isna().all():
        return None
    
    stats = {
        'mean': df[column].mean(),
        'median': df[column].median(),
        'std': df[column].std(),
        'min': df[column].min(),
        'max': df[column].max(),
        'count': df[column].count()
    }
    
    return stats

def format_metric_value(value, unit=''):
    """Format metric values for display"""
    if pd.isna(value):
        return "N/A"
    
    if isinstance(value, (int, float)):
        if value >= 1000:
            return f"{value:,.0f}{unit}"
        else:
            return f"{value:.1f}{unit}"
    else:
        return str(value) + unit