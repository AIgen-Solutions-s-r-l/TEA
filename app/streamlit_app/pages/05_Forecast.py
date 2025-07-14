import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np
from utils import load_data, create_station_filter, get_date_range

st.set_page_config(page_title="Forecast - Weather Data", page_icon="🔮", layout="wide")

st.title("🔮 Weather Forecast")
st.markdown("---")

# Filters
with st.sidebar:
    st.header("Filters")
    
    # Station selection
    station_id = create_station_filter()
    if not station_id:
        st.warning("Please select a specific station for forecasting")
    
    # Parameter selection
    st.subheader("Parameter")
    parameter = st.selectbox(
        "Select Parameter to Forecast",
        ["temperature", "humidity", "pressure", "wind_speed"]
    )
    
    # Forecast settings
    st.subheader("Forecast Settings")
    forecast_days = st.slider("Forecast Days", 1, 30, 7)
    
    # Advanced settings
    with st.expander("Advanced Settings"):
        seasonality_mode = st.selectbox(
            "Seasonality Mode",
            ["additive", "multiplicative"],
            help="Additive: seasonal fluctuations are constant. Multiplicative: seasonal fluctuations change proportionally"
        )
        
        include_holidays = st.checkbox("Include Holidays", value=False)
        
        changepoint_scale = st.slider(
            "Changepoint Scale",
            0.01, 0.5, 0.05,
            help="Higher values make the trend more flexible"
        )

# Main content
if station_id:
    # Load all available data for the station
    min_date, max_date = get_date_range()
    
    if min_date and max_date:
        df = load_data(min_date, max_date, station_id)
        
        if not df.empty and parameter in df.columns:
            # Prepare data for Prophet
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Aggregate to daily values for more stable forecasts
            daily_df = df.groupby(df['timestamp'].dt.date)[parameter].agg(['mean', 'min', 'max']).reset_index()
            daily_df.columns = ['date', f'{parameter}_mean', f'{parameter}_min', f'{parameter}_max']
            daily_df['date'] = pd.to_datetime(daily_df['date'])
            
            # Prepare data for Prophet (requires 'ds' and 'y' columns)
            prophet_df = daily_df[['date', f'{parameter}_mean']].copy()
            prophet_df.columns = ['ds', 'y']
            prophet_df = prophet_df.dropna()
            
            if len(prophet_df) > 30:  # Need sufficient data for forecasting
                # Split data for validation
                train_size = int(len(prophet_df) * 0.8)
                train_df = prophet_df[:train_size]
                test_df = prophet_df[train_size:]
                
                # Train Prophet model
                with st.spinner('Training forecast model...'):
                    model = Prophet(
                        seasonality_mode=seasonality_mode,
                        changepoint_prior_scale=changepoint_scale,
                        daily_seasonality=False,
                        weekly_seasonality=True,
                        yearly_seasonality=True
                    )
                    
                    if include_holidays:
                        # Add US holidays (can be customized)
                        model.add_country_holidays(country_name='US')
                    
                    model.fit(train_df)
                    
                    # Make predictions
                    future = model.make_future_dataframe(periods=forecast_days)
                    forecast = model.predict(future)
                
                # Forecast visualization
                st.subheader(f"📈 {parameter.capitalize()} Forecast for {station_id}")
                
                fig = go.Figure()
                
                # Historical data
                fig.add_trace(go.Scatter(
                    x=prophet_df['ds'],
                    y=prophet_df['y'],
                    mode='markers',
                    name='Historical',
                    marker=dict(size=4, color='blue')
                ))
                
                # Forecast
                fig.add_trace(go.Scatter(
                    x=forecast['ds'],
                    y=forecast['yhat'],
                    mode='lines',
                    name='Forecast',
                    line=dict(color='red')
                ))
                
                # Confidence intervals
                fig.add_trace(go.Scatter(
                    x=forecast['ds'],
                    y=forecast['yhat_upper'],
                    mode='lines',
                    name='Upper Bound',
                    line=dict(width=0),
                    showlegend=False
                ))
                
                fig.add_trace(go.Scatter(
                    x=forecast['ds'],
                    y=forecast['yhat_lower'],
                    mode='lines',
                    name='Lower Bound',
                    line=dict(width=0),
                    fill='tonexty',
                    fillcolor='rgba(255,0,0,0.2)',
                    showlegend=False
                ))
                
                # Add vertical line for forecast start
                fig.add_vline(
                    x=prophet_df['ds'].max(),
                    line_dash="dash",
                    line_color="gray",
                    annotation_text="Forecast Start"
                )
                
                fig.update_layout(
                    title=f'{parameter.capitalize()} Forecast - {station_id}',
                    xaxis_title='Date',
                    yaxis_title=parameter.capitalize(),
                    hovermode='x unified'
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Model components
                st.subheader("📊 Forecast Components")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Trend component
                    fig_trend = go.Figure()
                    fig_trend.add_trace(go.Scatter(
                        x=forecast['ds'],
                        y=forecast['trend'],
                        mode='lines',
                        name='Trend'
                    ))
                    fig_trend.update_layout(
                        title='Trend Component',
                        xaxis_title='Date',
                        yaxis_title='Trend'
                    )
                    st.plotly_chart(fig_trend, use_container_width=True)
                
                with col2:
                    # Weekly seasonality
                    fig_weekly = model.plot_components_plotly(forecast)
                    st.plotly_chart(fig_weekly, use_container_width=True)
                
                # Model performance
                if len(test_df) > 0:
                    st.subheader("📏 Model Performance")
                    
                    # Make predictions on test set
                    test_forecast = model.predict(test_df[['ds']])
                    
                    # Calculate metrics
                    mae = mean_absolute_error(test_df['y'], test_forecast['yhat'])
                    rmse = np.sqrt(mean_squared_error(test_df['y'], test_forecast['yhat']))
                    mape = np.mean(np.abs((test_df['y'] - test_forecast['yhat']) / test_df['y'])) * 100
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("MAE", f"{mae:.2f}")
                    with col2:
                        st.metric("RMSE", f"{rmse:.2f}")
                    with col3:
                        st.metric("MAPE", f"{mape:.1f}%")
                    
                    # Validation plot
                    fig_val = go.Figure()
                    
                    fig_val.add_trace(go.Scatter(
                        x=test_df['ds'],
                        y=test_df['y'],
                        mode='markers',
                        name='Actual',
                        marker=dict(color='blue')
                    ))
                    
                    fig_val.add_trace(go.Scatter(
                        x=test_forecast['ds'],
                        y=test_forecast['yhat'],
                        mode='lines',
                        name='Predicted',
                        line=dict(color='red')
                    ))
                    
                    fig_val.update_layout(
                        title='Model Validation on Test Set',
                        xaxis_title='Date',
                        yaxis_title=parameter.capitalize()
                    )
                    
                    st.plotly_chart(fig_val, use_container_width=True)
                
                # Forecast summary
                st.subheader("📋 Forecast Summary")
                
                future_dates = forecast[forecast['ds'] > prophet_df['ds'].max()]
                
                if not future_dates.empty:
                    summary_df = future_dates[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
                    summary_df.columns = ['Date', 'Forecast', 'Lower Bound', 'Upper Bound']
                    summary_df['Date'] = summary_df['Date'].dt.date
                    summary_df = summary_df.round(2)
                    
                    st.dataframe(summary_df, use_container_width=True)
                    
                    # Export forecast
                    csv = summary_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Forecast",
                        data=csv,
                        file_name=f"{parameter}_forecast_{station_id}_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                
                # Additional insights
                with st.expander("🔍 Additional Insights"):
                    st.markdown(f"""
                    ### Forecast Analysis for {parameter.capitalize()}
                    
                    **Station:** {station_id}
                    
                    **Key Findings:**
                    - The model detected {'multiplicative' if seasonality_mode == 'multiplicative' else 'additive'} seasonality
                    - Weekly patterns show {f"highest values on {forecast.loc[forecast['weekly'].idxmax(), 'ds'].strftime('%A')}" if 'weekly' in forecast.columns else "consistent weekly pattern"}
                    - Trend is {'increasing' if forecast['trend'].iloc[-1] > forecast['trend'].iloc[0] else 'decreasing'} over the forecast period
                    
                    **Forecast Range:**
                    - Next 7 days: {future_dates['yhat'][:7].mean():.1f} ± {(future_dates['yhat_upper'][:7].mean() - future_dates['yhat_lower'][:7].mean())/2:.1f}
                    - Minimum expected: {future_dates['yhat_lower'].min():.1f}
                    - Maximum expected: {future_dates['yhat_upper'].max():.1f}
                    """)
            
            else:
                st.warning(f"Insufficient data for forecasting. Need at least 30 days of data, found {len(prophet_df)} days.")
        
        else:
            st.error(f"No {parameter} data available for station {station_id}")
    
    else:
        st.error("Unable to determine date range from database")

else:
    st.info("Please select a specific weather station from the sidebar to generate forecasts.")