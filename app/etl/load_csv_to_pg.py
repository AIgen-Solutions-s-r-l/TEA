import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
import logging
from dotenv import load_dotenv
import glob

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'weather_db'),
    'user': os.getenv('DB_USER', 'weather_user'),
    'password': os.getenv('DB_PASSWORD', 'weather_password')
}

# Data directory
DATA_DIR = os.getenv('DATA_DIR', '/data')

def get_db_connection():
    """Create and return a database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

def load_csv_file(file_path):
    """Load a CSV file and prepare it for insertion"""
    try:
        # Try different encodings
        encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, sep=';', encoding=encoding)
                logger.info(f"Successfully read {file_path} with encoding {encoding}")
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            raise ValueError(f"Could not read file with any encoding: {encodings}")
        
        # Log the columns found in the CSV
        logger.info(f"Columns in {file_path}: {df.columns.tolist()}")
        
        # Map CSV columns to database columns - includes Italian column names
        column_mapping = {
            # English column names (most stations)
            'Time': 'timestamp',
            'latitude': 'latitude',
            'longitude': 'longitude',
            'extT': 'temperature',
            'rh': 'humidity',
            'pluv': 'precipitation',
            'wsp_ana': 'wind_speed',
            'wdir_ana': 'wind_direction',
            'radN': 'radiation',
            # Italian column names (station 263)
            'T aria (°C)': 'temperature',
            'T aria (�C)': 'temperature',  # With encoding issue
            'Umidità aria (%)': 'humidity',
            'Umidit� aria (%)': 'humidity',  # With encoding issue
            'pioggia (count)': 'precipitation_count',
            'pioggia (mm)': 'precipitation',
            'radiazione globale(W/m2)': 'radiation',
            'direzone vento (gradi)': 'wind_direction',
            'velocità vento (m/sec)': 'wind_speed',
            'velocit� vento (m/sec)': 'wind_speed',  # With encoding issue
        }
        
        # Create new dataframe with mapped columns
        new_df = pd.DataFrame()
        
        # Handle timestamp - check for both 'Time' and first column (Italian format)
        time_col = None
        if 'Time' in df.columns:
            time_col = 'Time'
        else:
            # For Italian format, timestamp might be the first column
            first_col = df.columns[0]
            if any(date_pattern in first_col.lower() for date_pattern in ['time', 'data', 'ora']):
                time_col = first_col
        
        if time_col:
            # Handle different date formats
            try:
                new_df['timestamp'] = pd.to_datetime(df[time_col], format='mixed', dayfirst=True)
            except:
                # Try different formats
                for fmt in ['%d/%m/%Y %H:%M', '%d-%b-%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S']:
                    try:
                        new_df['timestamp'] = pd.to_datetime(df[time_col], format=fmt)
                        break
                    except:
                        continue
        
        # Map all other columns
        for csv_col, db_col in column_mapping.items():
            if csv_col in df.columns and csv_col != time_col:
                if db_col in ['latitude', 'longitude']:
                    # Handle coordinate columns - they might have formatting issues
                    try:
                        new_df[db_col] = pd.to_numeric(df[csv_col].astype(str).str.replace(',', '.'), errors='coerce')
                    except:
                        new_df[db_col] = pd.to_numeric(df[csv_col], errors='coerce')
                elif db_col == 'precipitation_count':
                    # Integer column
                    new_df[db_col] = pd.to_numeric(df[csv_col], errors='coerce').fillna(0).astype('Int64')
                else:
                    # Regular numeric columns
                    new_df[db_col] = pd.to_numeric(df[csv_col], errors='coerce')
        
        # Add station_id from filename (e.g., smart256 -> 256)
        station_id = os.path.basename(file_path).replace('.csv', '').replace('smart', '')
        new_df['station_id'] = station_id
        
        # Add missing columns with NULL
        all_columns = ['timestamp', 'latitude', 'longitude', 'temperature', 'humidity', 
                      'pressure', 'wind_speed', 'wind_direction', 'precipitation', 
                      'precipitation_count', 'visibility', 'radiation', 'station_id']
        
        for col in all_columns:
            if col not in new_df.columns:
                new_df[col] = None
        
        # Replace NaN with None for proper NULL handling
        new_df = new_df.where(pd.notnull(new_df), None)
        
        # Select columns in correct order
        new_df = new_df[all_columns]
        
        logger.info(f"Loaded {len(new_df)} records from {file_path}")
        
        return new_df
    
    except Exception as e:
        logger.error(f"Failed to load CSV file {file_path}: {e}")
        raise

def insert_data_to_db(conn, df):
    """Insert DataFrame data into PostgreSQL"""
    try:
        cursor = conn.cursor()
        
        # Prepare the insert query
        columns = df.columns.tolist()
        query = f"""
            INSERT INTO weather_raw ({', '.join(columns)})
            VALUES %s
            ON CONFLICT DO NOTHING
        """
        
        # Convert DataFrame to list of tuples
        data = [tuple(row) for row in df.to_numpy()]
        
        # Execute batch insert
        execute_values(cursor, query, data)
        conn.commit()
        
        logger.info(f"Inserted {len(data)} records successfully")
        return len(data)
    
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to insert data: {e}")
        raise
    finally:
        cursor.close()

def process_all_csv_files():
    """Process all CSV files in the data directory"""
    # Find all CSV files
    csv_files = glob.glob(os.path.join(DATA_DIR, '*.csv'))
    
    if not csv_files:
        logger.warning(f"No CSV files found in {DATA_DIR}")
        return
    
    logger.info(f"Found {len(csv_files)} CSV files to process")
    
    # Get database connection
    conn = get_db_connection()
    
    try:
        total_records = 0
        
        for file_path in csv_files:
            logger.info(f"Processing file: {file_path}")
            
            try:
                # Load CSV file
                df = load_csv_file(file_path)
                
                # Insert data
                records = insert_data_to_db(conn, df)
                total_records += records
                
                # Optionally move processed file to archive
                archive_dir = os.path.join(DATA_DIR, 'processed')
                if not os.path.exists(archive_dir):
                    os.makedirs(archive_dir)
                
                archive_path = os.path.join(archive_dir, os.path.basename(file_path))
                os.rename(file_path, archive_path)
                logger.info(f"Moved processed file to: {archive_path}")
                
            except Exception as e:
                logger.error(f"Failed to process file {file_path}: {e}")
                continue
        
        logger.info(f"ETL completed. Total records inserted: {total_records}")
    
    finally:
        conn.close()

if __name__ == "__main__":
    logger.info("Starting ETL process...")
    process_all_csv_files()
    logger.info("ETL process completed")