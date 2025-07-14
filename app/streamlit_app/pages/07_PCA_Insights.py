"""
PCA Insights Dashboard Page
Visualizes Principal Component Analysis results for weather data patterns
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os

# Add the parent directory to the path to import analytics
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from analytics.pca_service import PCAAnalysisService
from utils import create_date_filter, create_station_filter, DB_CONFIG

st.set_page_config(page_title="PCA Insights - Weather Data", page_icon="🔍", layout="wide")

st.title("🔍 Principal Component Analysis Insights")
st.markdown("---")

# Sidebar filters
with st.sidebar:
    st.header("Filters")
    start_date, end_date = create_date_filter()
    station_id = create_station_filter()
    
    st.subheader("PCA Settings")
    
    # Parameters to analyze
    available_params = ["temperature", "humidity", "wind_speed", "wind_direction", "radiation", "precipitation"]
    selected_params = st.multiselect(
        "Select Parameters",
        available_params,
        default=["temperature", "humidity", "wind_speed", "radiation"],
        help="Select parameters for PCA analysis"
    )
    
    # Aggregation level
    aggregation = st.selectbox(
        "Time Aggregation",
        ["hourly", "daily"],
        help="Aggregate data before PCA analysis"
    )
    
    # Number of components
    auto_components = st.checkbox(
        "Auto-select components",
        value=True,
        help="Automatically determine number of components based on variance threshold"
    )
    
    if not auto_components:
        n_components = st.slider(
            "Number of Components",
            min_value=2,
            max_value=min(6, len(selected_params)),
            value=3,
            help="Fixed number of principal components"
        )
    else:
        n_components = None
        variance_threshold = st.slider(
            "Variance Threshold",
            min_value=0.80,
            max_value=0.99,
            value=0.95,
            step=0.01,
            help="Cumulative variance to capture"
        )

# Main content
if start_date and end_date and len(selected_params) >= 2:
    try:
        # Initialize PCA service
        pca_service = PCAAnalysisService(DB_CONFIG)
        
        # Load and prepare data
        with st.spinner("Loading and preparing weather data..."):
            X_scaled, original_df, feature_names = pca_service.prepare_data_for_pca(
                start_date=start_date,
                end_date=end_date,
                station_id=station_id,
                parameters=selected_params,
                aggregation=aggregation
            )
        
        if not X_scaled.empty:
            st.success(f"Loaded {len(X_scaled):,} observations with {len(feature_names)} features")
            
            # Perform PCA
            with st.spinner("Performing PCA analysis..."):
                pca_results = pca_service.perform_pca(
                    X_scaled=X_scaled,
                    n_components=n_components,
                    variance_threshold=variance_threshold if auto_components else 0.95
                )
            
            # Display PCA overview
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Components Selected",
                    pca_results['n_components'],
                    help="Number of principal components"
                )
            
            with col2:
                st.metric(
                    "Variance Explained",
                    f"{pca_results['cumulative_variance_ratio'][-1]:.1%}",
                    help="Total variance captured by all components"
                )
            
            with col3:
                st.metric(
                    "Dimensionality Reduction",
                    f"{len(feature_names)} → {pca_results['n_components']}",
                    help="Original vs reduced dimensions"
                )
            
            # Variance explained plot
            st.subheader("📊 Variance Explained")
            
            variance_df = pd.DataFrame({
                'Component': [f'PC{i+1}' for i in range(pca_results['n_components'])],
                'Individual': pca_results['explained_variance_ratio'],
                'Cumulative': pca_results['cumulative_variance_ratio']
            })
            
            fig_variance = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Individual variance
            fig_variance.add_trace(
                go.Bar(
                    x=variance_df['Component'],
                    y=variance_df['Individual'],
                    name='Individual Variance',
                    marker_color='lightblue'
                ),
                secondary_y=False
            )
            
            # Cumulative variance
            fig_variance.add_trace(
                go.Scatter(
                    x=variance_df['Component'],
                    y=variance_df['Cumulative'],
                    mode='lines+markers',
                    name='Cumulative Variance',
                    line=dict(color='red', width=3),
                    marker=dict(size=8)
                ),
                secondary_y=True
            )
            
            fig_variance.update_xaxes(title_text="Principal Component")
            fig_variance.update_yaxes(title_text="Individual Variance Explained", secondary_y=False)
            fig_variance.update_yaxes(title_text="Cumulative Variance Explained", secondary_y=True)
            fig_variance.update_layout(
                title="Variance Explained by Principal Components",
                height=400,
                hovermode='x unified'
            )
            
            st.plotly_chart(fig_variance, use_container_width=True)
            
            # Component loadings heatmap
            st.subheader("🔥 Component Loadings")
            st.markdown("*How much each original parameter contributes to each principal component*")
            
            components_df = pca_results['components']
            
            fig_loadings = px.imshow(
                components_df.T.values,
                x=components_df.index,
                y=components_df.columns,
                color_continuous_scale='RdBu_r',
                aspect='auto',
                title='Principal Component Loadings',
                zmin=-1,
                zmax=1
            )
            
            # Add loading values as text
            for i, component in enumerate(components_df.columns):
                for j, feature in enumerate(components_df.index):
                    loading = components_df.loc[feature, component]
                    text_color = 'white' if abs(loading) > 0.5 else 'black'
                    
                    fig_loadings.add_annotation(
                        x=j, y=i,
                        text=f"{loading:.2f}",
                        showarrow=False,
                        font=dict(color=text_color, size=10)
                    )
            
            fig_loadings.update_layout(height=400)
            st.plotly_chart(fig_loadings, use_container_width=True)
            
            # Top contributors analysis
            st.subheader("🎯 Top Contributing Features")
            
            top_contributors = pca_service.identify_top_contributors(
                components_df=components_df,
                n_top=3
            )
            
            # Create columns for each component
            n_cols = min(3, pca_results['n_components'])
            cols = st.columns(n_cols)
            
            for i, (pc, contributors) in enumerate(list(top_contributors.items())[:n_cols]):
                with cols[i]:
                    st.markdown(f"**{pc}** ({pca_results['explained_variance_ratio'][i]:.1%} variance)")
                    
                    for rank, (feature, loading) in enumerate(contributors, 1):
                        direction = "↗️" if loading > 0 else "↘️"
                        st.write(f"{rank}. {direction} **{feature}** ({loading:+.3f})")
            
            # PCA Scores visualization (2D projection)
            st.subheader("📈 Data Projection (PCA Scores)")
            
            col1, col2 = st.columns(2)
            
            with col1:
                pc_x = st.selectbox(
                    "X-axis Component",
                    [f"PC{i+1}" for i in range(pca_results['n_components'])],
                    index=0
                )
            
            with col2:
                pc_y = st.selectbox(
                    "Y-axis Component",
                    [f"PC{i+1}" for i in range(pca_results['n_components'])],
                    index=1 if pca_results['n_components'] > 1 else 0
                )
            
            # Create scatter plot of scores
            scores_df = pca_results['transformed_data']
            
            fig_scores = px.scatter(
                x=scores_df[pc_x],
                y=scores_df[pc_y],
                title=f"PCA Scores: {pc_x} vs {pc_y}",
                labels={
                    'x': f"{pc_x} ({pca_results['explained_variance_ratio'][int(pc_x[2:])-1]:.1%} variance)",
                    'y': f"{pc_y} ({pca_results['explained_variance_ratio'][int(pc_y[2:])-1]:.1%} variance)"
                },
                opacity=0.6
            )
            
            fig_scores.update_layout(height=500)
            st.plotly_chart(fig_scores, use_container_width=True)
            
            # Biplot
            with st.expander("📊 PCA Biplot"):
                st.markdown("Combined view of data points and feature vectors")
                
                scale_factor = st.slider(
                    "Vector Scale Factor",
                    min_value=1.0,
                    max_value=5.0,
                    value=3.0,
                    step=0.5,
                    help="Scale factor for feature vectors"
                )
                
                # Create biplot data
                biplot_data = pca_service.create_biplot_data(
                    pca_results=pca_results,
                    pc_x=int(pc_x[2:]),
                    pc_y=int(pc_y[2:]),
                    scale_factor=scale_factor
                )
                
                # Create biplot
                fig_biplot = go.Figure()
                
                # Add scores (data points)
                fig_biplot.add_trace(go.Scatter(
                    x=biplot_data['scores']['x'],
                    y=biplot_data['scores']['y'],
                    mode='markers',
                    name='Observations',
                    marker=dict(size=4, opacity=0.6),
                    hovertemplate='PC1: %{x:.2f}<br>PC2: %{y:.2f}<extra></extra>'
                ))
                
                # Add feature vectors
                for i, feature in enumerate(biplot_data['loadings']['features']):
                    x_load = biplot_data['loadings']['x'][i]
                    y_load = biplot_data['loadings']['y'][i]
                    
                    # Arrow
                    fig_biplot.add_trace(go.Scatter(
                        x=[0, x_load],
                        y=[0, y_load],
                        mode='lines',
                        line=dict(color='red', width=2),
                        showlegend=False,
                        hoverinfo='skip'
                    ))
                    
                    # Feature label
                    fig_biplot.add_trace(go.Scatter(
                        x=[x_load],
                        y=[y_load],
                        mode='text',
                        text=[feature],
                        textposition='middle center',
                        showlegend=False,
                        textfont=dict(color='red', size=12),
                        hoverinfo='skip'
                    ))
                
                fig_biplot.update_layout(
                    title=f"PCA Biplot: {pc_x} vs {pc_y}",
                    xaxis_title=f"{pc_x} ({biplot_data['variance_explained'][pc_x]:.1%} variance)",
                    yaxis_title=f"{pc_y} ({biplot_data['variance_explained'][pc_y]:.1%} variance)",
                    height=600,
                    showlegend=True
                )
                
                st.plotly_chart(fig_biplot, use_container_width=True)
            
            # Anomaly detection
            with st.expander("🚨 Anomaly Detection"):
                st.markdown("Identify unusual patterns using PCA reconstruction error")
                
                threshold_percentile = st.slider(
                    "Anomaly Threshold (percentile)",
                    min_value=90,
                    max_value=99,
                    value=95,
                    help="Percentile threshold for anomaly detection"
                )
                
                # Calculate reconstruction error
                error_df = pca_service.calculate_reconstruction_error(X_scaled, pca_results)
                anomaly_df = pca_service.detect_anomalies(
                    error_df, 
                    threshold_percentile=threshold_percentile/100
                )
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(
                        "Total Anomalies",
                        int(anomaly_df['is_anomaly'].sum()),
                        help="Number of detected anomalies"
                    )
                
                with col2:
                    st.metric(
                        "Anomaly Rate",
                        f"{anomaly_df['is_anomaly'].mean():.1%}",
                        help="Percentage of anomalous observations"
                    )
                
                with col3:
                    st.metric(
                        "Max Anomaly Score",
                        f"{anomaly_df['anomaly_score'].max():.2f}",
                        help="Highest anomaly score detected"
                    )
                
                # Reconstruction error plot
                fig_error = px.histogram(
                    anomaly_df,
                    x='reconstruction_error',
                    nbins=50,
                    title='Distribution of Reconstruction Errors',
                    color='is_anomaly',
                    color_discrete_map={True: 'red', False: 'blue'}
                )
                
                # Add threshold line
                threshold = anomaly_df['reconstruction_error'].quantile(threshold_percentile/100)
                fig_error.add_vline(
                    x=threshold,
                    line_dash="dash",
                    line_color="red",
                    annotation_text=f"Threshold ({threshold_percentile}th percentile)"
                )
                
                st.plotly_chart(fig_error, use_container_width=True)
                
                # Show anomalous observations
                if anomaly_df['is_anomaly'].any():
                    st.subheader("Detected Anomalies")
                    
                    anomalies = anomaly_df[anomaly_df['is_anomaly']].copy()
                    anomalies['timestamp'] = original_df.loc[anomalies['index'], 'timestamp'].values
                    
                    # Sort by anomaly score
                    anomalies = anomalies.sort_values('anomaly_score', ascending=False)
                    
                    # Display top anomalies
                    display_cols = ['timestamp', 'reconstruction_error', 'anomaly_score']
                    st.dataframe(
                        anomalies[display_cols].head(10),
                        use_container_width=True,
                        hide_index=True
                    )
            
            # Temporal patterns analysis
            with st.expander("⏰ Temporal Patterns in Components"):
                st.markdown("Analyze how principal components vary over time")
                
                # Analyze temporal patterns
                temporal_patterns = pca_service.analyze_temporal_patterns(
                    transformed_df=pca_results['transformed_data'],
                    original_df=original_df
                )
                
                # Plot temporal patterns
                pattern_type = st.selectbox(
                    "Pattern Type",
                    ["hourly_pattern", "daily_pattern", "monthly_pattern"],
                    format_func=lambda x: x.replace('_', ' ').title()
                )
                
                # Create subplot for each component
                n_components = min(3, pca_results['n_components'])
                fig_temporal = make_subplots(
                    rows=n_components,
                    cols=1,
                    subplot_titles=[f"PC{i+1}" for i in range(n_components)],
                    shared_xaxes=True
                )
                
                for i in range(n_components):
                    pc = f"PC{i+1}"
                    pattern_data = temporal_patterns[pc][pattern_type]
                    
                    x_vals = list(pattern_data.keys())
                    y_vals = list(pattern_data.values())
                    
                    fig_temporal.add_trace(
                        go.Scatter(
                            x=x_vals,
                            y=y_vals,
                            mode='lines+markers',
                            name=pc,
                            line=dict(width=2)
                        ),
                        row=i+1,
                        col=1
                    )
                
                fig_temporal.update_layout(
                    title=f"Temporal Patterns: {pattern_type.replace('_', ' ').title()}",
                    height=600,
                    showlegend=False
                )
                
                st.plotly_chart(fig_temporal, use_container_width=True)
            
            # Generate PCA report
            if st.button("📄 Generate PCA Report"):
                # Get top contributors and anomaly summary
                anomaly_summary = {
                    'total_anomalies': int(anomaly_df['is_anomaly'].sum()),
                    'anomaly_rate': float(anomaly_df['is_anomaly'].mean())
                }
                
                # Generate report
                report = pca_service.generate_pca_report(
                    pca_results=pca_results,
                    top_contributors=top_contributors,
                    anomaly_summary=anomaly_summary
                )
                
                st.download_button(
                    label="📥 Download Report",
                    data=report,
                    file_name=f"pca_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.txt",
                    mime="text/plain"
                )
        
        else:
            st.warning("No data available for the selected filters and parameters.")
            
    except Exception as e:
        st.error(f"Error performing PCA analysis: {str(e)}")
        st.exception(e)

else:
    if not start_date or not end_date:
        st.info("Please select a valid date range to begin PCA analysis.")
    elif len(selected_params) < 2:
        st.info("Please select at least 2 parameters for PCA analysis.")

# Information sidebar
with st.sidebar:
    st.markdown("---")
    st.subheader("📖 About PCA")
    
    with st.expander("Understanding PCA"):
        st.markdown("""
        **Principal Component Analysis:**
        - Reduces data dimensionality
        - Identifies patterns in high-dimensional data
        - Creates uncorrelated components
        - Preserves maximum variance
        
        **Component Loadings:**
        - Show feature contribution to each PC
        - Values range from -1 to +1
        - Higher absolute values = stronger influence
        
        **Variance Explained:**
        - How much information each PC captures
        - First PC captures most variance
        - Cumulative variance shows total captured
        """)
    
    with st.expander("Anomaly Detection"):
        st.markdown("""
        **Reconstruction Error:**
        - Measures how well PCA reconstructs original data
        - High error = unusual pattern
        - Based on reduced dimensionality
        
        **Anomaly Score:**
        - Normalized reconstruction error
        - Values > 1.0 indicate anomalies
        - Higher scores = more unusual patterns
        """)
    
    with st.expander("Interpretation Tips"):
        st.markdown("""
        **Component Analysis:**
        - PC1 usually captures dominant weather pattern
        - PC2 captures secondary variations
        - Look for meteorological relationships
        
        **Biplot Reading:**
        - Points = individual observations
        - Arrows = original variables
        - Arrow length = variable importance
        - Arrow direction = relationship
        """)