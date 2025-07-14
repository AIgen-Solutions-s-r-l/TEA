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
        ["temperature", "humidity", "wind_speed", "wind_direction", "radiation", "precipitation"]
    )
    
    # Forecast settings
    st.subheader("Forecast Settings")
    forecast_days = st.slider("Forecast Days", 1, 365, 30, 
                             help="Number of days to forecast into the future")
    
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
                
                # Split historical and future data
                last_historical_date = prophet_df['ds'].max()
                historical_forecast = forecast[forecast['ds'] <= last_historical_date]
                future_forecast = forecast[forecast['ds'] > last_historical_date]
                
                # Historical data points
                fig.add_trace(go.Scatter(
                    x=prophet_df['ds'],
                    y=prophet_df['y'],
                    mode='markers',
                    name='Historical Data',
                    marker=dict(size=4, color='blue')
                ))
                
                # Model fit on historical data
                fig.add_trace(go.Scatter(
                    x=historical_forecast['ds'],
                    y=historical_forecast['yhat'],
                    mode='lines',
                    name='Model Fit',
                    line=dict(color='green', width=2)
                ))
                
                # Future forecast
                fig.add_trace(go.Scatter(
                    x=future_forecast['ds'],
                    y=future_forecast['yhat'],
                    mode='lines',
                    name='Forecast',
                    line=dict(color='red', width=3, dash='dash')
                ))
                
                # Confidence intervals for future forecast only
                fig.add_trace(go.Scatter(
                    x=future_forecast['ds'],
                    y=future_forecast['yhat_upper'],
                    mode='lines',
                    name='Upper Bound',
                    line=dict(width=0),
                    showlegend=False
                ))
                
                fig.add_trace(go.Scatter(
                    x=future_forecast['ds'],
                    y=future_forecast['yhat_lower'],
                    mode='lines',
                    name='Lower Bound',
                    line=dict(width=0),
                    fill='tonexty',
                    fillcolor='rgba(255,0,0,0.2)',
                    showlegend=False
                ))
                
                # Note: Vertical line removed due to Plotly datetime compatibility issue
                
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
                    st.subheader("Weekly Pattern")
                    if 'weekly' in forecast.columns:
                        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                        weekly_data = forecast[['ds', 'weekly']].copy()
                        weekly_data['day_of_week'] = weekly_data['ds'].dt.day_name()
                        weekly_pattern = weekly_data.groupby('day_of_week')['weekly'].mean().reindex(days)
                        
                        fig_weekly = go.Figure()
                        fig_weekly.add_trace(go.Scatter(
                            x=days,
                            y=weekly_pattern.values,
                            mode='lines+markers',
                            name='Weekly Effect',
                            line=dict(color='green', width=3)
                        ))
                        fig_weekly.update_layout(
                            xaxis_title='Day of Week',
                            yaxis_title='Weekly Effect',
                            height=300
                        )
                        st.plotly_chart(fig_weekly, use_container_width=True)
                    else:
                        st.info("No weekly seasonality detected")
                
                # Model performance
                if len(test_df) > 0:
                    st.subheader("📏 Model Performance")
                    
                    # Make predictions on test set
                    test_forecast = model.predict(test_df[['ds']])
                    
                    # Merge test data with forecast to ensure alignment
                    test_comparison = test_df.merge(test_forecast[['ds', 'yhat']], on='ds', how='inner')
                    
                    # Calculate metrics
                    mae = mean_absolute_error(test_comparison['y'], test_comparison['yhat'])
                    rmse = np.sqrt(mean_squared_error(test_comparison['y'], test_comparison['yhat']))
                    
                    # Calculate MAPE, handling division by zero
                    non_zero_mask = test_comparison['y'] != 0
                    if non_zero_mask.any():
                        mape = np.mean(np.abs((test_comparison['y'][non_zero_mask] - test_comparison['yhat'][non_zero_mask]) / test_comparison['y'][non_zero_mask])) * 100
                    else:
                        mape = np.nan
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("MAE", f"{mae:.2f}")
                    with col2:
                        st.metric("RMSE", f"{rmse:.2f}")
                    with col3:
                        if not np.isnan(mape):
                            st.metric("MAPE", f"{mape:.1f}%")
                        else:
                            st.metric("MAPE", "N/A", help="Cannot calculate MAPE due to zero values")
                    
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
                    # Show key metrics
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        avg_forecast = future_dates['yhat'].mean()
                        st.metric("Average Forecast", f"{avg_forecast:.1f}")
                    
                    with col2:
                        max_forecast = future_dates['yhat'].max()
                        max_date = future_dates.loc[future_dates['yhat'].idxmax(), 'ds']
                        st.metric("Maximum", f"{max_forecast:.1f}", 
                                delta=f"on {max_date.strftime('%Y-%m-%d')}")
                    
                    with col3:
                        min_forecast = future_dates['yhat'].min()
                        min_date = future_dates.loc[future_dates['yhat'].idxmin(), 'ds']
                        st.metric("Minimum", f"{min_forecast:.1f}",
                                delta=f"on {min_date.strftime('%Y-%m-%d')}")
                    
                    with col4:
                        trend_change = future_dates['yhat'].iloc[-1] - future_dates['yhat'].iloc[0]
                        st.metric("Trend Change", f"{trend_change:+.1f}",
                                help="Change from start to end of forecast period")
                    
                    # Detailed forecast table
                    st.markdown("#### Detailed Forecast")
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
                    # Trend analysis
                    historical_mean = prophet_df['y'].mean()
                    forecast_mean = future_dates['yhat'].mean()
                    trend_direction = "increasing" if forecast_mean > historical_mean else "decreasing"
                    
                    # Uncertainty analysis
                    avg_uncertainty = (future_dates['yhat_upper'] - future_dates['yhat_lower']).mean()
                    uncertainty_pct = (avg_uncertainty / forecast_mean) * 100
                    
                    # Seasonality strength
                    if 'weekly' in forecast.columns:
                        weekly_effect = forecast['weekly'].std()
                        seasonality_strength = "strong" if weekly_effect > 0.5 else "moderate" if weekly_effect > 0.2 else "weak"
                    else:
                        seasonality_strength = "not detected"
                    
                    st.markdown(f"""
                    ### Forecast Analysis for {parameter.capitalize()}
                    
                    **Station:** {station_id}
                    
                    **Key Findings:**
                    - **Trend**: The {parameter} is {trend_direction} ({forecast_mean:.1f} vs historical {historical_mean:.1f})
                    - **Uncertainty**: Average prediction interval width is ±{avg_uncertainty:.1f} ({uncertainty_pct:.1f}%)
                    - **Seasonality**: Weekly pattern is {seasonality_strength}
                    - **Model Type**: Using {seasonality_mode} seasonality mode
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