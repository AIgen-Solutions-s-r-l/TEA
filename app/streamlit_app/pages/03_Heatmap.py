import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from utils import load_data, create_date_filter, get_stations

st.set_page_config(page_title="Heatmap - Weather Data", page_icon="🗺️", layout="wide")

st.title("🗺️ Weather Heatmap Visualization")
st.markdown("---")

# Filters
with st.sidebar:
    st.header("Filters")
    start_date, end_date = create_date_filter()
    
    # Parameter selection
    st.subheader("Parameter")
    parameter = st.selectbox(
        "Select Parameter",
        ["temperature", "humidity", "pressure", "wind_speed", "precipitation"]
    )
    
    # Heatmap type
    st.subheader("Heatmap Type")
    heatmap_type = st.selectbox(
        "Select Type",
        ["Station vs Time", "Hour vs Day", "Month vs Year"]
    )

# Load data
if start_date and end_date:
    # For station comparison, don't filter by station
    df = load_data(start_date, end_date, None)
    
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        if heatmap_type == "Station vs Time":
            st.subheader(f"📊 {parameter.capitalize()} by Station Over Time")
            
            # Aggregate by day and station
            df['date'] = df['timestamp'].dt.date
            pivot_data = df.pivot_table(
                values=parameter,
                index='station_id',
                columns='date',
                aggfunc='mean'
            )
            
            if not pivot_data.empty:
                fig = px.imshow(
                    pivot_data,
                    labels=dict(x="Date", y="Station", color=parameter.capitalize()),
                    x=pivot_data.columns,
                    y=pivot_data.index,
                    color_continuous_scale='RdBu_r' if parameter == 'temperature' else 'Viridis'
                )
                
                fig.update_layout(
                    title=f'{parameter.capitalize()} Heatmap by Station',
                    xaxis_tickangle=-45,
                    height=400 + len(pivot_data.index) * 20
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Station statistics
                st.subheader("📈 Station Statistics")
                
                station_stats = df.groupby('station_id')[parameter].agg(['mean', 'std', 'min', 'max'])
                station_stats = station_stats.round(2)
                station_stats = station_stats.sort_values('mean', ascending=False)
                
                st.dataframe(station_stats, use_container_width=True)
        
        elif heatmap_type == "Hour vs Day":
            st.subheader(f"📊 {parameter.capitalize()} by Hour of Day")
            
            # Extract hour and day of week
            df['hour'] = df['timestamp'].dt.hour
            df['day_of_week'] = df['timestamp'].dt.day_name()
            
            # Define day order
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            # Create pivot table
            pivot_data = df.pivot_table(
                values=parameter,
                index='day_of_week',
                columns='hour',
                aggfunc='mean'
            )
            
            # Reorder by day of week
            pivot_data = pivot_data.reindex(day_order)
            
            if not pivot_data.empty:
                fig = px.imshow(
                    pivot_data,
                    labels=dict(x="Hour of Day", y="Day of Week", color=parameter.capitalize()),
                    x=list(range(24)),
                    y=day_order,
                    color_continuous_scale='RdBu_r' if parameter == 'temperature' else 'Viridis'
                )
                
                fig.update_layout(
                    title=f'Average {parameter.capitalize()} by Hour and Day of Week',
                    xaxis=dict(tickmode='linear', tick0=0, dtick=1)
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Hourly patterns
                col1, col2 = st.columns(2)
                
                with col1:
                    # Average by hour
                    hourly_avg = df.groupby('hour')[parameter].mean()
                    fig_hourly = px.line(
                        x=hourly_avg.index,
                        y=hourly_avg.values,
                        title=f'Average {parameter.capitalize()} by Hour',
                        labels={'x': 'Hour', 'y': parameter.capitalize()}
                    )
                    st.plotly_chart(fig_hourly, use_container_width=True)
                
                with col2:
                    # Average by day of week
                    daily_avg = df.groupby('day_of_week')[parameter].mean().reindex(day_order)
                    fig_daily = px.bar(
                        x=daily_avg.index,
                        y=daily_avg.values,
                        title=f'Average {parameter.capitalize()} by Day of Week',
                        labels={'x': 'Day', 'y': parameter.capitalize()}
                    )
                    st.plotly_chart(fig_daily, use_container_width=True)
        
        else:  # Month vs Year
            st.subheader(f"📊 {parameter.capitalize()} by Month and Year")
            
            # Extract month and year
            df['month'] = df['timestamp'].dt.month_name()
            df['year'] = df['timestamp'].dt.year
            
            # Define month order
            month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December']
            
            # Create pivot table
            pivot_data = df.pivot_table(
                values=parameter,
                index='month',
                columns='year',
                aggfunc='mean'
            )
            
            # Reorder by month
            available_months = [m for m in month_order if m in pivot_data.index]
            pivot_data = pivot_data.reindex(available_months)
            
            if not pivot_data.empty:
                fig = px.imshow(
                    pivot_data,
                    labels=dict(x="Year", y="Month", color=parameter.capitalize()),
                    x=pivot_data.columns,
                    y=available_months,
                    color_continuous_scale='RdBu_r' if parameter == 'temperature' else 'Viridis'
                )
                
                fig.update_layout(
                    title=f'Average {parameter.capitalize()} by Month and Year'
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Seasonal analysis
                st.subheader("🌍 Seasonal Analysis")
                
                # Define seasons
                def get_season(month):
                    if month in [12, 1, 2]:
                        return 'Winter'
                    elif month in [3, 4, 5]:
                        return 'Spring'
                    elif month in [6, 7, 8]:
                        return 'Summer'
                    else:
                        return 'Fall'
                
                df['season'] = df['timestamp'].dt.month.apply(get_season)
                
                seasonal_stats = df.groupby('season')[parameter].agg(['mean', 'std', 'min', 'max'])
                seasonal_stats = seasonal_stats.round(2)
                
                # Reorder seasons
                season_order = ['Winter', 'Spring', 'Summer', 'Fall']
                seasonal_stats = seasonal_stats.reindex(season_order)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.dataframe(seasonal_stats, use_container_width=True)
                
                with col2:
                    fig_season = px.bar(
                        x=seasonal_stats.index,
                        y=seasonal_stats['mean'],
                        error_y=seasonal_stats['std'],
                        title=f'Average {parameter.capitalize()} by Season',
                        labels={'x': 'Season', 'y': f'Average {parameter.capitalize()}'}
                    )
                    st.plotly_chart(fig_season, use_container_width=True)
        
        # Data export
        with st.expander("💾 Export Data"):
            if heatmap_type == "Station vs Time":
                csv = pivot_data.to_csv()
                filename = f"{parameter}_station_time_heatmap.csv"
            elif heatmap_type == "Hour vs Day":
                csv = pivot_data.to_csv()
                filename = f"{parameter}_hour_day_heatmap.csv"
            else:
                csv = pivot_data.to_csv()
                filename = f"{parameter}_month_year_heatmap.csv"
            
            st.download_button(
                label="📥 Download Heatmap Data",
                data=csv,
                file_name=filename,
                mime="text/csv"
            )
    
    else:
        st.info("No data available for the selected filters.")
else:
    st.warning("Please select a valid date range to view the heatmap.")