"""
Correlations Analysis Dashboard Page
Visualizes multivariate correlations between weather parameters
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.figure_factory as ff
from plotly.subplots import make_subplots
import sys
import os

# Add the parent directory to the path to import analytics
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from analytics.correlation_service import CorrelationAnalysisService
from utils import create_date_filter, create_station_filter, DB_CONFIG

st.set_page_config(page_title="Correlations - Weather Data", page_icon="🔗", layout="wide")

st.title("🔗 Weather Parameter Correlations")
st.markdown("---")

# Sidebar filters
with st.sidebar:
    st.header("Filters")
    start_date, end_date = create_date_filter()
    station_id = create_station_filter()
    
    st.subheader("Analysis Settings")
    
    # Correlation method
    correlation_method = st.selectbox(
        "Correlation Method",
        ["both", "pearson", "spearman"],
        help="Pearson for linear relationships, Spearman for monotonic relationships"
    )
    
    # Parameters to analyze
    st.subheader("Parameters")
    available_params = ["temperature", "humidity", "wind_speed", "wind_direction", "radiation", "precipitation"]
    selected_params = st.multiselect(
        "Select Parameters",
        available_params,
        default=["temperature", "humidity", "wind_speed", "radiation"],
        help="Select at least 2 parameters for correlation analysis"
    )
    
    # Significance threshold
    significance_threshold = st.slider(
        "Significance Threshold (p-value)",
        min_value=0.01,
        max_value=0.10,
        value=0.05,
        step=0.01,
        help="Maximum p-value for statistical significance"
    )
    
    # Strong correlation threshold
    correlation_threshold = st.slider(
        "Strong Correlation Threshold",
        min_value=0.3,
        max_value=0.9,
        value=0.7,
        step=0.1,
        help="Minimum absolute correlation to highlight"
    )

# Main content
if start_date and end_date and len(selected_params) >= 2:
    try:
        # Initialize correlation service
        correlation_service = CorrelationAnalysisService(DB_CONFIG)
        
        # Load data
        with st.spinner("Loading weather data..."):
            df = correlation_service.load_weather_data(
                start_date=start_date,
                end_date=end_date,
                station_id=station_id,
                parameters=selected_params
            )
        
        if not df.empty:
            st.success(f"Loaded {len(df):,} observations")
            
            # Calculate correlations
            with st.spinner("Calculating correlations..."):
                correlation_results = correlation_service.calculate_correlations(
                    df=df,
                    method=correlation_method,
                    min_observations=30
                )
            
            # Main correlation matrices
            if correlation_method in ['pearson', 'both'] and 'pearson' in correlation_results:
                st.subheader("📊 Pearson Correlation Matrix")
                st.markdown("*Measures linear relationships between variables*")
                
                pearson_corr = correlation_results['pearson']
                pearson_pvals = correlation_results.get('pearson_pvalues')
                
                # Create correlation heatmap
                fig_pearson = px.imshow(
                    pearson_corr.values,
                    x=pearson_corr.columns,
                    y=pearson_corr.index,
                    color_continuous_scale='RdBu_r',
                    aspect='auto',
                    title='Pearson Correlation Coefficients',
                    zmin=-1,
                    zmax=1
                )
                
                # Add correlation values as text
                for i, row in enumerate(pearson_corr.index):
                    for j, col in enumerate(pearson_corr.columns):
                        corr_val = pearson_corr.loc[row, col]
                        pval = pearson_pvals.loc[row, col] if pearson_pvals is not None else None
                        
                        # Color text based on significance
                        text_color = 'white' if abs(corr_val) > 0.5 else 'black'
                        
                        # Add significance indicator
                        text = f"{corr_val:.2f}"
                        if pval is not None and pval < significance_threshold:
                            text += "*"
                        
                        fig_pearson.add_annotation(
                            x=j, y=i,
                            text=text,
                            showarrow=False,
                            font=dict(color=text_color, size=10)
                        )
                
                fig_pearson.update_layout(height=500)
                st.plotly_chart(fig_pearson, use_container_width=True)
                
                # Add note about significance
                st.caption(f"* indicates p < {significance_threshold} (statistically significant)")
            
            if correlation_method in ['spearman', 'both'] and 'spearman' in correlation_results:
                st.subheader("📈 Spearman Correlation Matrix")
                st.markdown("*Measures monotonic relationships between variables*")
                
                spearman_corr = correlation_results['spearman']
                spearman_pvals = correlation_results.get('spearman_pvalues')
                
                # Create correlation heatmap
                fig_spearman = px.imshow(
                    spearman_corr.values,
                    x=spearman_corr.columns,
                    y=spearman_corr.index,
                    color_continuous_scale='RdBu_r',
                    aspect='auto',
                    title='Spearman Correlation Coefficients',
                    zmin=-1,
                    zmax=1
                )
                
                # Add correlation values as text
                for i, row in enumerate(spearman_corr.index):
                    for j, col in enumerate(spearman_corr.columns):
                        corr_val = spearman_corr.loc[row, col]
                        pval = spearman_pvals.loc[row, col] if spearman_pvals is not None else None
                        
                        text_color = 'white' if abs(corr_val) > 0.5 else 'black'
                        
                        text = f"{corr_val:.2f}"
                        if pval is not None and pval < significance_threshold:
                            text += "*"
                        
                        fig_spearman.add_annotation(
                            x=j, y=i,
                            text=text,
                            showarrow=False,
                            font=dict(color=text_color, size=10)
                        )
                
                fig_spearman.update_layout(height=500)
                st.plotly_chart(fig_spearman, use_container_width=True)
            
            # Strong correlations summary
            st.subheader("🔍 Strong Correlations Identified")
            
            strong_correlations_found = False
            
            for method in ['pearson', 'spearman']:
                if method in correlation_results:
                    corr_matrix = correlation_results[method]
                    pval_matrix = correlation_results.get(f"{method}_pvalues")
                    
                    strong_corr = correlation_service.identify_strong_correlations(
                        correlation_matrix=corr_matrix,
                        pvalue_matrix=pval_matrix,
                        threshold=correlation_threshold,
                        pvalue_threshold=significance_threshold
                    )
                    
                    if strong_corr:
                        strong_correlations_found = True
                        st.markdown(f"**{method.capitalize()} Correlations:**")
                        
                        for var1, var2, corr, pval in strong_corr:
                            # Determine strength and direction
                            if abs(corr) >= 0.9:
                                strength = "Very Strong"
                                color = "red" if corr < 0 else "green"
                            elif abs(corr) >= 0.7:
                                strength = "Strong"
                                color = "orange" if corr < 0 else "blue"
                            else:
                                strength = "Moderate"
                                color = "gray"
                            
                            direction = "Positive" if corr > 0 else "Negative"
                            
                            # Create metric display
                            col1, col2, col3 = st.columns([2, 1, 1])
                            
                            with col1:
                                st.markdown(f"**{var1}** ↔ **{var2}**")
                            
                            with col2:
                                st.metric(
                                    label="Correlation",
                                    value=f"{corr:+.3f}",
                                    help=f"{strength} {direction.lower()} correlation"
                                )
                            
                            with col3:
                                if pval is not None:
                                    st.metric(
                                        label="p-value",
                                        value=f"{pval:.4f}",
                                        help="Statistical significance"
                                    )
            
            if not strong_correlations_found:
                st.info(f"No correlations found above threshold of {correlation_threshold:.1f}")
            
            # Scatter plot matrix for strong correlations
            if strong_correlations_found:
                st.subheader("📊 Scatter Plot Matrix")
                
                # Get the most correlated parameters
                all_strong_params = set()
                for method in ['pearson', 'spearman']:
                    if method in correlation_results:
                        corr_matrix = correlation_results[method]
                        strong_corr = correlation_service.identify_strong_correlations(
                            correlation_matrix=corr_matrix,
                            threshold=correlation_threshold
                        )
                        
                        for var1, var2, _, _ in strong_corr[:3]:  # Top 3
                            all_strong_params.add(var1)
                            all_strong_params.add(var2)
                
                if len(all_strong_params) >= 2:
                    strong_params_list = list(all_strong_params)[:4]  # Limit to 4 for readability
                    
                    # Create scatter plot matrix
                    scatter_df = df[strong_params_list].copy()
                    
                    fig_scatter = ff.create_scatterplotmatrix(
                        scatter_df,
                        diag='histogram',
                        height=600,
                        width=800,
                        title="Scatter Plot Matrix - Most Correlated Parameters"
                    )
                    
                    st.plotly_chart(fig_scatter, use_container_width=True)
            
            # Temporal correlation analysis
            with st.expander("🕒 Temporal Correlation Stability"):
                st.markdown("Analyze how correlations change over time")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    window_days = st.number_input(
                        "Analysis Window (days)",
                        min_value=7,
                        max_value=90,
                        value=30,
                        help="Size of sliding window for temporal analysis"
                    )
                
                with col2:
                    step_days = st.number_input(
                        "Step Size (days)",
                        min_value=1,
                        max_value=30,
                        value=7,
                        help="Step size between windows"
                    )
                
                if st.button("Analyze Temporal Stability"):
                    with st.spinner("Analyzing temporal correlation stability..."):
                        temporal_results = correlation_service.analyze_temporal_stability(
                            start_date=start_date,
                            end_date=end_date,
                            window_days=window_days,
                            step_days=step_days,
                            station_id=station_id,
                            parameters=selected_params
                        )
                    
                    if temporal_results['windows']:
                        # Plot temporal correlation changes
                        fig_temporal = go.Figure()
                        
                        window_dates = [w['start'] for w in temporal_results['windows']]
                        
                        for correlation_pair, methods in temporal_results['correlations'].items():
                            if methods['pearson']:  # Only plot if we have data
                                fig_temporal.add_trace(go.Scatter(
                                    x=window_dates,
                                    y=methods['pearson'],
                                    mode='lines+markers',
                                    name=correlation_pair.replace('_vs_', ' vs '),
                                    line=dict(width=2)
                                ))
                        
                        fig_temporal.update_layout(
                            title='Correlation Stability Over Time (Pearson)',
                            xaxis_title='Date',
                            yaxis_title='Correlation Coefficient',
                            height=400,
                            hovermode='x unified'
                        )
                        
                        st.plotly_chart(fig_temporal, use_container_width=True)
                        
                        # Summary statistics
                        st.subheader("Temporal Stability Summary")
                        stability_data = []
                        
                        for correlation_pair, methods in temporal_results['correlations'].items():
                            if methods['pearson']:
                                pearson_values = np.array(methods['pearson'])
                                stability_data.append({
                                    'Parameter Pair': correlation_pair.replace('_vs_', ' vs '),
                                    'Mean Correlation': f"{np.mean(pearson_values):.3f}",
                                    'Std Deviation': f"{np.std(pearson_values):.3f}",
                                    'Min': f"{np.min(pearson_values):.3f}",
                                    'Max': f"{np.max(pearson_values):.3f}"
                                })
                        
                        if stability_data:
                            stability_df = pd.DataFrame(stability_data)
                            st.dataframe(stability_df, use_container_width=True, hide_index=True)
                    else:
                        st.warning("Insufficient data for temporal analysis")
            
            # Download correlation report
            if st.button("📄 Generate Correlation Report"):
                # Get strong correlations for all methods
                all_strong_correlations = []
                for method in ['pearson', 'spearman']:
                    if method in correlation_results:
                        corr_matrix = correlation_results[method]
                        pval_matrix = correlation_results.get(f"{method}_pvalues")
                        
                        strong_corr = correlation_service.identify_strong_correlations(
                            correlation_matrix=corr_matrix,
                            pvalue_matrix=pval_matrix,
                            threshold=correlation_threshold
                        )
                        all_strong_correlations.extend(strong_corr)
                
                # Generate report
                report = correlation_service.generate_correlation_report(
                    correlation_results=correlation_results,
                    strong_correlations=all_strong_correlations
                )
                
                st.download_button(
                    label="📥 Download Report",
                    data=report,
                    file_name=f"correlation_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.txt",
                    mime="text/plain"
                )
        
        else:
            st.warning("No data available for the selected filters and parameters.")
            
    except Exception as e:
        st.error(f"Error performing correlation analysis: {str(e)}")
        st.exception(e)

else:
    if not start_date or not end_date:
        st.info("Please select a valid date range to begin correlation analysis.")
    elif len(selected_params) < 2:
        st.info("Please select at least 2 parameters for correlation analysis.")

# Information sidebar
with st.sidebar:
    st.markdown("---")
    st.subheader("📖 About Correlations")
    
    with st.expander("Understanding Correlation Methods"):
        st.markdown("""
        **Pearson Correlation:**
        - Measures linear relationships
        - Values: -1 (perfect negative) to +1 (perfect positive)
        - Best for normally distributed data
        
        **Spearman Correlation:**
        - Measures monotonic relationships
        - Values: -1 to +1
        - More robust to outliers
        - Works with non-linear relationships
        
        **Interpretation:**
        - |r| ≥ 0.9: Very strong
        - |r| ≥ 0.7: Strong  
        - |r| ≥ 0.5: Moderate
        - |r| ≥ 0.3: Weak
        - |r| < 0.3: Very weak
        """)
    
    with st.expander("Statistical Significance"):
        st.markdown("""
        **P-value interpretation:**
        - p < 0.05: Statistically significant
        - p < 0.01: Highly significant
        - p ≥ 0.05: Not significant
        
        Correlations marked with * are statistically significant at your chosen threshold.
        """)