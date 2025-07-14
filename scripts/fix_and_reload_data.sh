#!/bin/bash

echo "=== Fixing Integer Overflow and Reloading Data ==="

# Apply the migration to fix wind_direction column
echo "1. Applying database migration..."
docker-compose exec -T db psql -U weather_user -d weather_db < postgres/migrations/001_fix_wind_direction_overflow.sql

if [ $? -eq 0 ]; then
    echo "✅ Migration applied successfully"
else
    echo "❌ Migration failed. Please check the error messages above."
    exit 1
fi

# Check if there are any CSV files in the RAW_DATA directory that need to be reprocessed
echo -e "\n2. Checking for unprocessed CSV files..."
if ls RAW_DATA/*.csv 1> /dev/null 2>&1; then
    echo "Found CSV files to process:"
    ls -la RAW_DATA/*.csv
    
    # Copy files to the data directory
    echo -e "\n3. Copying CSV files to container data directory..."
    docker cp RAW_DATA/. weather_db:/data/
    
    # Run the ETL process
    echo -e "\n4. Running ETL to load all data..."
    docker-compose exec dashboard python app/etl/load_csv_to_pg.py
    
    echo -e "\n✅ Data loading complete!"
else
    echo "No CSV files found in RAW_DATA directory"
    echo "Looking for processed files to reload..."
    
    # Check if there are processed files
    if docker-compose exec db ls /data/processed/*.csv 1> /dev/null 2>&1; then
        echo -e "\n3. Moving processed files back for reloading..."
        docker-compose exec db sh -c 'mv /data/processed/*.csv /data/'
        
        echo -e "\n4. Running ETL to reload all data..."
        docker-compose exec dashboard python app/etl/load_csv_to_pg.py
        
        echo -e "\n✅ Data reloading complete!"
    else
        echo "No processed files found either. Please ensure your CSV files are in the RAW_DATA directory."
    fi
fi

# Show final record count
echo -e "\n5. Checking final record count..."
docker-compose exec -T db psql -U weather_user -d weather_db -c "SELECT COUNT(*) as total_records FROM weather_raw;"
docker-compose exec -T db psql -U weather_user -d weather_db -c "SELECT station_id, COUNT(*) as records FROM weather_raw GROUP BY station_id ORDER BY station_id;"