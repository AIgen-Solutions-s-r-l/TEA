import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import load_data, create_date_filter, create_station_filter, get_summary_statistics, format_metric_value

st.set_page_config(page_title="Overview - Weather Data", page_icon="📊", layout="wide")

st.title("📊 Weather Overview")
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
        # Key metrics
        st.subheader("📈 Key Metrics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            temp_stats = get_summary_statistics(df, 'temperature')
            if temp_stats:
                st.metric(
                    "Average Temperature",
                    format_metric_value(temp_stats['mean'], '°C'),
                    f"Range: {format_metric_value(temp_stats['min'])}°C - {format_metric_value(temp_stats['max'])}°C"
                )
        
        with col2:
            humidity_stats = get_summary_statistics(df, 'humidity')
            if humidity_stats:
                st.metric(
                    "Average Humidity",
                    format_metric_value(humidity_stats['mean'], '%'),
                    f"Std: {format_metric_value(humidity_stats['std'])}%"
                )
        
        with col3:
            wind_stats = get_summary_statistics(df, 'wind_speed')
            if wind_stats:
                st.metric(
                    "Average Wind Speed",
                    format_metric_value(wind_stats['mean'], ' m/s'),
                    f"Max: {format_metric_value(wind_stats['max'])} m/s"
                )
        
        with col4:
            precip_stats = get_summary_statistics(df, 'precipitation')
            if precip_stats:
                st.metric(
                    "Total Precipitation",
                    format_metric_value(df['precipitation'].sum(), ' mm'),
                    f"Days with rain: {(df['precipitation'] > 0).sum()}"
                )
        
        # Temperature and Humidity Chart
        st.subheader("🌡️ Temperature and Humidity Over Time")
        
        fig = go.Figure()
        
        # Add temperature trace
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['temperature'],
            mode='lines',
            name='Temperature (°C)',
            yaxis='y',
            line=dict(color='red')
        ))
        
        # Add humidity trace
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['humidity'],
            mode='lines',
            name='Humidity (%)',
            yaxis='y2',
            line=dict(color='blue')
        ))
        
        # Update layout
        fig.update_layout(
            title='Temperature and Humidity Trends',
            xaxis_title='Date',
            yaxis=dict(
                title='Temperature (°C)',
                titlefont=dict(color='red'),
                tickfont=dict(color='red')
            ),
            yaxis2=dict(
                title='Humidity (%)',
                titlefont=dict(color='blue'),
                tickfont=dict(color='blue'),
                anchor='x',
                overlaying='y',
                side='right'
            ),
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Weather Parameters Distribution
        st.subheader("📊 Weather Parameters Distribution")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Temperature distribution
            fig_temp = px.histogram(
                df, x='temperature', nbins=30,
                title='Temperature Distribution',
                labels={'temperature': 'Temperature (°C)', 'count': 'Frequency'}
            )
            st.plotly_chart(fig_temp, use_container_width=True)
        
        with col2:
            # Wind speed distribution
            fig_wind = px.histogram(
                df, x='wind_speed', nbins=30,
                title='Wind Speed Distribution',
                labels={'wind_speed': 'Wind Speed (m/s)', 'count': 'Frequency'}
            )
            st.plotly_chart(fig_wind, use_container_width=True)
        
        # Correlation Matrix
        st.subheader("🔗 Parameter Correlations")
        
        numeric_cols = ['temperature', 'humidity', 'wind_speed', 'wind_direction', 'radiation', 'precipitation']
        available_cols = [col for col in numeric_cols if col in df.columns and df[col].notna().any()]
        
        if len(available_cols) > 1:
            corr_matrix = df[available_cols].corr()
            
            fig_corr = px.imshow(
                corr_matrix,
                labels=dict(color="Correlation"),
                x=available_cols,
                y=available_cols,
                color_continuous_scale='RdBu_r',
                zmin=-1,
                zmax=1
            )
            fig_corr.update_layout(title="Correlation Matrix of Weather Parameters")
            st.plotly_chart(fig_corr, use_container_width=True)
        
        # Raw data table
        with st.expander("📋 View Raw Data"):
            st.dataframe(df, use_container_width=True)
            
            # Download button
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download Data as CSV",
                data=csv,
                file_name=f"weather_data_{start_date}_{end_date}.csv",
                mime="text/csv"
            )
    
    else:
        st.info("No data available for the selected filters.")
else:
    st.warning("Please select a valid date range to view the overview.")