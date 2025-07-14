import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils import load_data, create_date_filter, create_station_filter

st.set_page_config(page_title="Trends - Weather Data", page_icon="📈", layout="wide")

st.title("📈 Weather Trends Analysis")
st.markdown("---")

# Filters
with st.sidebar:
    st.header("Filters")
    start_date, end_date = create_date_filter()
    station_id = create_station_filter()
    
    # Aggregation options
    st.subheader("Aggregation")
    agg_type = st.selectbox(
        "Aggregation Level",
        ["Hourly", "Daily", "Weekly", "Monthly"]
    )
    
    # Parameters to plot
    st.subheader("Parameters")
    params = st.multiselect(
        "Select Parameters",
        ["temperature", "humidity", "wind_speed", "wind_direction", "radiation", "precipitation"],
        default=["temperature", "humidity"]
    )

# Load data
if start_date and end_date and params:
    df = load_data(start_date, end_date, station_id)
    
    if not df.empty:
        # Aggregate data based on selection
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        if agg_type == "Hourly":
            df_agg = df.set_index('timestamp').resample('H').agg({
                'temperature': 'mean',
                'humidity': 'mean',
                'wind_speed': 'mean',
                'wind_direction': 'mean',
                'radiation': 'mean',
                'precipitation': 'sum'
            }).reset_index()
        elif agg_type == "Daily":
            df_agg = df.set_index('timestamp').resample('D').agg({
                'temperature': ['mean', 'min', 'max'],
                'humidity': 'mean',
                'wind_speed': 'mean',
                'wind_direction': 'mean',
                'radiation': 'mean',
                'precipitation': 'sum'
            }).reset_index()
            df_agg.columns = ['_'.join(col).strip() if col[1] else col[0] for col in df_agg.columns.values]
            df_agg = df_agg.rename(columns={'timestamp_': 'timestamp'})
        elif agg_type == "Weekly":
            df_agg = df.set_index('timestamp').resample('W').agg({
                'temperature': 'mean',
                'humidity': 'mean',
                'wind_speed': 'mean',
                'wind_direction': 'mean',
                'radiation': 'mean',
                'precipitation': 'sum'
            }).reset_index()
        else:  # Monthly
            df_agg = df.set_index('timestamp').resample('M').agg({
                'temperature': 'mean',
                'humidity': 'mean',
                'wind_speed': 'mean',
                'wind_direction': 'mean',
                'radiation': 'mean',
                'precipitation': 'sum'
            }).reset_index()
        
        # Multi-parameter line chart
        st.subheader("📊 Multi-Parameter Trends")
        
        fig = make_subplots(
            rows=len(params), cols=1,
            shared_xaxes=True,
            subplot_titles=params,
            vertical_spacing=0.1
        )
        
        colors = ['blue', 'red', 'green', 'orange', 'purple']
        
        for i, param in enumerate(params):
            if param in df_agg.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df_agg['timestamp'],
                        y=df_agg[param],
                        mode='lines',
                        name=param.capitalize(),
                        line=dict(color=colors[i % len(colors)])
                    ),
                    row=i+1, col=1
                )
                
                # Add min/max bands for daily temperature
                if agg_type == "Daily" and param == "temperature" and 'temperature_min' in df_agg.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=df_agg['timestamp'],
                            y=df_agg['temperature_max'],
                            mode='lines',
                            name='Max Temp',
                            line=dict(color='rgba(255,0,0,0.3)'),
                            showlegend=False
                        ),
                        row=i+1, col=1
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=df_agg['timestamp'],
                            y=df_agg['temperature_min'],
                            mode='lines',
                            name='Min Temp',
                            line=dict(color='rgba(0,0,255,0.3)'),
                            fill='tonexty',
                            showlegend=False
                        ),
                        row=i+1, col=1
                    )
        
        fig.update_xaxes(title_text="Date", row=len(params), col=1)
        fig.update_layout(height=300*len(params), showlegend=True)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Moving averages
        st.subheader("📈 Moving Averages")
        
        col1, col2 = st.columns(2)
        
        with col1:
            ma_param = st.selectbox("Select Parameter for Moving Average", params)
        
        with col2:
            ma_windows = st.multiselect(
                "Moving Average Windows",
                [7, 14, 30],
                default=[7, 14]
            )
        
        if ma_param and ma_windows:
            fig_ma = go.Figure()
            
            # Original data
            fig_ma.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df[ma_param],
                mode='lines',
                name='Original',
                line=dict(color='lightgray', width=1)
            ))
            
            # Moving averages
            colors_ma = ['blue', 'red', 'green']
            for i, window in enumerate(ma_windows):
                ma_data = df[ma_param].rolling(window=window*24).mean()  # Assuming hourly data
                fig_ma.add_trace(go.Scatter(
                    x=df['timestamp'],
                    y=ma_data,
                    mode='lines',
                    name=f'{window}-day MA',
                    line=dict(color=colors_ma[i % len(colors_ma)], width=2)
                ))
            
            fig_ma.update_layout(
                title=f'{ma_param.capitalize()} with Moving Averages',
                xaxis_title='Date',
                yaxis_title=ma_param.capitalize(),
                hovermode='x unified'
            )
            
            st.plotly_chart(fig_ma, use_container_width=True)
        
        # Trend decomposition
        if agg_type in ["Daily", "Weekly", "Monthly"]:
            st.subheader("🔍 Trend Decomposition")
            
            decomp_param = st.selectbox("Select Parameter for Decomposition", params)
            
            if decomp_param and decomp_param in df_agg.columns:
                from statsmodels.tsa.seasonal import seasonal_decompose
                
                # Ensure we have enough data points
                if len(df_agg) > 2 * (7 if agg_type == "Daily" else 4):
                    try:
                        # Perform decomposition
                        decomposition = seasonal_decompose(
                            df_agg[decomp_param].dropna(),
                            model='additive',
                            period=7 if agg_type == "Daily" else 4
                        )
                        
                        # Create subplots
                        fig_decomp = make_subplots(
                            rows=4, cols=1,
                            subplot_titles=['Original', 'Trend', 'Seasonal', 'Residual'],
                            shared_xaxes=True,
                            vertical_spacing=0.05
                        )
                        
                        # Add traces
                        fig_decomp.add_trace(
                            go.Scatter(x=df_agg['timestamp'], y=df_agg[decomp_param], name='Original'),
                            row=1, col=1
                        )
                        fig_decomp.add_trace(
                            go.Scatter(x=df_agg['timestamp'], y=decomposition.trend, name='Trend'),
                            row=2, col=1
                        )
                        fig_decomp.add_trace(
                            go.Scatter(x=df_agg['timestamp'], y=decomposition.seasonal, name='Seasonal'),
                            row=3, col=1
                        )
                        fig_decomp.add_trace(
                            go.Scatter(x=df_agg['timestamp'], y=decomposition.resid, name='Residual'),
                            row=4, col=1
                        )
                        
                        fig_decomp.update_layout(height=800, showlegend=False)
                        fig_decomp.update_xaxes(title_text="Date", row=4, col=1)
                        
                        st.plotly_chart(fig_decomp, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Unable to perform decomposition: {e}")
        
        # Summary statistics
        with st.expander("📊 Summary Statistics"):
            st.dataframe(df_agg.describe(), use_container_width=True)
    
    else:
        st.info("No data available for the selected filters.")
else:
    st.warning("Please select a valid date range and at least one parameter to view trends.")