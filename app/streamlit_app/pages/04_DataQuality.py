import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from utils import load_data, create_date_filter, create_station_filter, get_db_connection

st.set_page_config(page_title="Data Quality - Weather Data", page_icon="🔍", layout="wide")

st.title("🔍 Data Quality Analysis")
st.markdown("---")

# Filters
with st.sidebar:
    st.header("Filters")
    start_date, end_date = create_date_filter()
    station_id = create_station_filter()

# Load data
if start_date and end_date:
    df = load_data(start_date, end_date, station_id)
    
    if not df.empty:
        # Data completeness overview
        st.subheader("📊 Data Completeness Overview")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_records = len(df)
            st.metric("Total Records", f"{total_records:,}")
        
        with col2:
            date_range = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1
            expected_records = date_range * 24  # Assuming hourly data
            if station_id:
                expected_records *= 1
            else:
                # Get number of stations
                stations = df['station_id'].nunique()
                expected_records *= stations
            completeness = (total_records / expected_records * 100) if expected_records > 0 else 0
            st.metric("Data Completeness", f"{completeness:.1f}%")
        
        with col3:
            missing_total = df.isnull().sum().sum()
            missing_pct = (missing_total / (len(df) * len(df.columns)) * 100)
            st.metric("Overall Missing Data", f"{missing_pct:.1f}%")
        
        # Missing data by column
        st.subheader("🔎 Missing Data Analysis")
        
        missing_data = pd.DataFrame({
            'Column': df.columns,
            'Missing Count': df.isnull().sum(),
            'Missing Percentage': (df.isnull().sum() / len(df) * 100).round(2)
        })
        missing_data = missing_data[missing_data['Missing Count'] > 0].sort_values('Missing Percentage', ascending=False)
        
        if not missing_data.empty:
            fig_missing = px.bar(
                missing_data,
                x='Column',
                y='Missing Percentage',
                title='Missing Data by Column',
                labels={'Missing Percentage': 'Missing %'},
                color='Missing Percentage',
                color_continuous_scale='Reds'
            )
            st.plotly_chart(fig_missing, use_container_width=True)
        else:
            st.success("✅ No missing data found!")
        
        # Data quality metrics by parameter
        st.subheader("📈 Data Quality Metrics")
        
        weather_params = ['temperature', 'humidity', 'pressure', 'wind_speed', 'precipitation', 'visibility']
        available_params = [p for p in weather_params if p in df.columns]
        
        if available_params:
            # Create subplots for each parameter
            fig = make_subplots(
                rows=2, cols=3,
                subplot_titles=available_params[:6],
                specs=[[{'type': 'box'}, {'type': 'box'}, {'type': 'box'}],
                       [{'type': 'box'}, {'type': 'box'}, {'type': 'box'}]]
            )
            
            for i, param in enumerate(available_params[:6]):
                row = i // 3 + 1
                col = i % 3 + 1
                
                fig.add_trace(
                    go.Box(y=df[param].dropna(), name=param, showlegend=False),
                    row=row, col=col
                )
            
            fig.update_layout(height=600, title_text="Parameter Distribution and Outliers")
            st.plotly_chart(fig, use_container_width=True)
        
        # Data validity checks
        st.subheader("✅ Data Validity Checks")
        
        validity_checks = []
        
        # Temperature range check
        if 'temperature' in df.columns:
            invalid_temp = df[(df['temperature'] < -50) | (df['temperature'] > 60)].shape[0]
            validity_checks.append({
                'Check': 'Temperature Range (-50°C to 60°C)',
                'Invalid Records': invalid_temp,
                'Status': '✅ Pass' if invalid_temp == 0 else '❌ Fail'
            })
        
        # Humidity range check
        if 'humidity' in df.columns:
            invalid_humidity = df[(df['humidity'] < 0) | (df['humidity'] > 100)].shape[0]
            validity_checks.append({
                'Check': 'Humidity Range (0% to 100%)',
                'Invalid Records': invalid_humidity,
                'Status': '✅ Pass' if invalid_humidity == 0 else '❌ Fail'
            })
        
        # Pressure range check
        if 'pressure' in df.columns:
            invalid_pressure = df[(df['pressure'] < 800) | (df['pressure'] > 1100)].shape[0]
            validity_checks.append({
                'Check': 'Pressure Range (800 to 1100 hPa)',
                'Invalid Records': invalid_pressure,
                'Status': '✅ Pass' if invalid_pressure == 0 else '❌ Fail'
            })
        
        # Wind speed check
        if 'wind_speed' in df.columns:
            invalid_wind = df[df['wind_speed'] < 0].shape[0]
            validity_checks.append({
                'Check': 'Wind Speed (≥ 0 m/s)',
                'Invalid Records': invalid_wind,
                'Status': '✅ Pass' if invalid_wind == 0 else '❌ Fail'
            })
        
        # Display validity checks
        validity_df = pd.DataFrame(validity_checks)
        st.dataframe(validity_df, use_container_width=True, hide_index=True)
        
        # Time series continuity
        st.subheader("⏱️ Time Series Continuity")
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df_sorted = df.sort_values('timestamp')
        
        if station_id:
            # Single station analysis
            time_diffs = df_sorted['timestamp'].diff().dropna()
            
            # Expected frequency (assuming hourly)
            expected_freq = pd.Timedelta(hours=1)
            gaps = time_diffs[time_diffs > expected_freq]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Data Gaps Detected", len(gaps))
                
                if len(gaps) > 0:
                    st.write("**Largest Gaps:**")
                    largest_gaps = gaps.nlargest(5)
                    gap_info = pd.DataFrame({
                        'Gap Duration': largest_gaps,
                        'Start Time': df_sorted.loc[largest_gaps.index - 1, 'timestamp'].values,
                        'End Time': df_sorted.loc[largest_gaps.index, 'timestamp'].values
                    })
                    st.dataframe(gap_info, use_container_width=True)
            
            with col2:
                # Visualize data availability
                df_hourly = df_sorted.set_index('timestamp').resample('H').size()
                
                fig_availability = go.Figure()
                fig_availability.add_trace(go.Scatter(
                    x=df_hourly.index,
                    y=df_hourly.values,
                    mode='lines',
                    fill='tozeroy',
                    name='Records per Hour'
                ))
                fig_availability.update_layout(
                    title='Data Availability Over Time',
                    xaxis_title='Date',
                    yaxis_title='Records per Hour'
                )
                st.plotly_chart(fig_availability, use_container_width=True)
        
        else:
            # Multiple stations analysis
            station_completeness = []
            
            for station in df['station_id'].unique():
                station_df = df[df['station_id'] == station].sort_values('timestamp')
                expected_hours = date_range * 24
                actual_hours = len(station_df)
                completeness = (actual_hours / expected_hours * 100) if expected_hours > 0 else 0
                
                station_completeness.append({
                    'Station': station,
                    'Expected Records': expected_hours,
                    'Actual Records': actual_hours,
                    'Completeness %': completeness
                })
            
            station_comp_df = pd.DataFrame(station_completeness).sort_values('Completeness %', ascending=False)
            
            fig_station_comp = px.bar(
                station_comp_df,
                x='Station',
                y='Completeness %',
                title='Data Completeness by Station',
                color='Completeness %',
                color_continuous_scale='RdYlGn'
            )
            st.plotly_chart(fig_station_comp, use_container_width=True)
        
        # Data quality report
        with st.expander("📄 Generate Data Quality Report"):
            report = f"""
# Data Quality Report

**Date Range:** {start_date} to {end_date}
**Station:** {station_id if station_id else 'All Stations'}
**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary Statistics
- Total Records: {total_records:,}
- Data Completeness: {completeness:.1f}%
- Overall Missing Data: {missing_pct:.1f}%

## Missing Data by Column
{missing_data.to_string() if not missing_data.empty else 'No missing data found.'}

## Data Validity Checks
{validity_df.to_string(index=False)}

## Recommendations
"""
            if missing_pct > 10:
                report += "\n- High percentage of missing data detected. Consider data imputation strategies."
            
            if len(validity_checks) > 0 and any(check['Invalid Records'] > 0 for check in validity_checks):
                report += "\n- Invalid values detected. Review data collection procedures and implement validation rules."
            
            if len(gaps) > 10:
                report += "\n- Multiple data gaps detected. Investigate sensor reliability and data transmission issues."
            
            st.text_area("Report", report, height=400)
            
            st.download_button(
                label="📥 Download Report",
                data=report,
                file_name=f"data_quality_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )
    
    else:
        st.info("No data available for the selected filters.")
else:
    st.warning("Please select a valid date range to analyze data quality.")