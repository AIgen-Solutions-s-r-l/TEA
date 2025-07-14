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
        # Read CSV file
        df = pd.read_csv(file_path)
        
        # Expected columns mapping
        column_mapping = {
            'timestamp': 'timestamp',
            'temperature': 'temperature',
            'humidity': 'humidity',
            'pressure': 'pressure',
            'wind_speed': 'wind_speed',
            'wind_direction': 'wind_direction',
            'precipitation': 'precipitation',
            'visibility': 'visibility',
            'station_id': 'station_id'
        }
        
        # Rename columns if necessary
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
        
        # Convert timestamp to datetime
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Add station_id if not present (extract from filename)
        if 'station_id' not in df.columns:
            station_id = os.path.basename(file_path).split('_')[0]
            df['station_id'] = station_id
        
        # Select only required columns
        required_columns = list(column_mapping.values())
        available_columns = [col for col in required_columns if col in df.columns]
        df = df[available_columns]
        
        # Replace NaN with None for proper NULL handling
        df = df.where(pd.notnull(df), None)
        
        return df
    
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