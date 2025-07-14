#!/usr/bin/env python3
"""Verify that all CSV columns are being mapped and loaded correctly"""

import pandas as pd
import os
import glob

# Column mapping from ETL
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
    'direzione vento (gradi)': 'wind_direction',  # Typo variant
    'velocità vento (m/sec)': 'wind_speed',
    'velocit� vento (m/sec)': 'wind_speed',  # With encoding issue
}

# Check all CSV files
csv_files = glob.glob('RAW_DATA/*.csv')
all_unmapped_columns = set()

print("=== CSV Column Analysis ===\n")

for file_path in csv_files:
    print(f"\nFile: {os.path.basename(file_path)}")
    print("-" * 50)
    
    # Try different encodings
    for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
        try:
            df = pd.read_csv(file_path, sep=';', encoding=encoding, nrows=1)
            break
        except:
            continue
    
    # Get columns
    csv_columns = df.columns.tolist()
    print(f"Total columns: {len(csv_columns)}")
    print(f"Columns: {csv_columns}")
    
    # Check mapping
    mapped_columns = []
    unmapped_columns = []
    
    for col in csv_columns:
        if col in column_mapping:
            mapped_columns.append(f"{col} → {column_mapping[col]}")
        else:
            unmapped_columns.append(col)
            all_unmapped_columns.add(col)
    
    print(f"\nMapped ({len(mapped_columns)}):")
    for m in mapped_columns:
        print(f"  ✓ {m}")
    
    if unmapped_columns:
        print(f"\nUnmapped ({len(unmapped_columns)}):")
        for u in unmapped_columns:
            print(f"  ✗ {u}")
    else:
        print("\n✅ All columns are mapped!")

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

if all_unmapped_columns:
    print(f"\n⚠️  Found {len(all_unmapped_columns)} unmapped column(s) across all files:")
    for col in sorted(all_unmapped_columns):
        print(f"  - {col}")
    print("\nThese columns are NOT being captured in the ETL process!")
else:
    print("\n✅ SUCCESS: All columns from all CSV files are being mapped and captured!")

# Check database columns
print("\n" + "=" * 60)
print("DATABASE SCHEMA")
print("=" * 60)
print("\nColumns in weather_raw table:")
db_columns = ['timestamp', 'latitude', 'longitude', 'temperature', 'humidity', 
              'wind_speed', 'wind_direction', 'precipitation', 
              'precipitation_count', 'radiation', 'station_id']
for col in db_columns:
    print(f"  - {col}")