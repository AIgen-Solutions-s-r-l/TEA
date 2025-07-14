"""
Principal Component Analysis (PCA) Service
Implements PCA for dimensionality reduction and pattern discovery in weather data
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
import psycopg2
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PCAAnalysisService:
    """Service for Principal Component Analysis of weather data"""
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize the PCA analysis service
        
        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        self.scaler = StandardScaler()
        self.imputer = SimpleImputer(strategy='mean')
        
    def get_db_connection(self):
        """Create and return a database connection"""
        return psycopg2.connect(**self.db_config)
    
    def prepare_data_for_pca(
        self,
        start_date: datetime,
        end_date: datetime,
        station_id: Optional[str] = None,
        parameters: Optional[List[str]] = None,
        aggregation: str = 'hourly'
    ) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
        """
        Load and prepare weather data for PCA
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            station_id: Optional specific station ID
            parameters: Optional list of parameters to include
            aggregation: Time aggregation level ('hourly', 'daily')
            
        Returns:
            Tuple of (scaled data, original data, feature names)
        """
        if parameters is None:
            parameters = ['temperature', 'humidity', 'wind_speed', 
                         'wind_direction', 'radiation', 'precipitation']
        
        # Load data
        query = f"""
        SELECT timestamp, station_id, {', '.join(parameters)}
        FROM weather_raw
        WHERE timestamp BETWEEN %s AND %s
        """
        params = [start_date, end_date]
        
        if station_id:
            query += " AND station_id = %s"
            params.append(station_id)
            
        query += " ORDER BY timestamp"
        
        with self.get_db_connection() as conn:
            df = pd.read_sql(query, conn, params=params)
        
        # Aggregate if needed
        if aggregation == 'daily':
            df['date'] = pd.to_datetime(df['timestamp']).dt.date
            numeric_cols = [col for col in parameters if col in df.columns]
            
            agg_dict = {col: 'mean' for col in numeric_cols}
            agg_dict['station_id'] = 'first'
            
            df = df.groupby('date').agg(agg_dict).reset_index()
            df['timestamp'] = pd.to_datetime(df['date'])
        
        # Prepare features
        feature_cols = [col for col in parameters if col in df.columns]
        X = df[feature_cols].copy()
        
        # Handle missing values
        X_imputed = self.imputer.fit_transform(X)
        
        # Standardize features
        X_scaled = self.scaler.fit_transform(X_imputed)
        
        # Create DataFrame with scaled data
        X_scaled_df = pd.DataFrame(
            X_scaled, 
            columns=feature_cols,
            index=df.index
        )
        
        return X_scaled_df, df, feature_cols
    
    def perform_pca(
        self,
        X_scaled: pd.DataFrame,
        n_components: Optional[int] = None,
        variance_threshold: float = 0.95
    ) -> Dict:
        """
        Perform PCA analysis
        
        Args:
            X_scaled: Standardized feature matrix
            n_components: Number of components (None for automatic)
            variance_threshold: Cumulative variance threshold for auto selection
            
        Returns:
            Dictionary with PCA results
        """
        # Determine number of components
        if n_components is None:
            # First fit to get all components
            pca_full = PCA()
            pca_full.fit(X_scaled)
            
            # Find number of components for variance threshold
            cumsum_var = np.cumsum(pca_full.explained_variance_ratio_)
            n_components = np.argmax(cumsum_var >= variance_threshold) + 1
            
        # Fit PCA with selected components
        pca = PCA(n_components=n_components)
        X_transformed = pca.fit_transform(X_scaled)
        
        # Create components DataFrame
        components_df = pd.DataFrame(
            pca.components_.T,
            columns=[f'PC{i+1}' for i in range(n_components)],
            index=X_scaled.columns
        )
        
        # Create transformed data DataFrame
        transformed_df = pd.DataFrame(
            X_transformed,
            columns=[f'PC{i+1}' for i in range(n_components)],
            index=X_scaled.index
        )
        
        results = {
            'n_components': n_components,
            'explained_variance': pca.explained_variance_,
            'explained_variance_ratio': pca.explained_variance_ratio_,
            'cumulative_variance_ratio': np.cumsum(pca.explained_variance_ratio_),
            'components': components_df,
            'transformed_data': transformed_df,
            'feature_names': list(X_scaled.columns),
            'mean': self.scaler.mean_,
            'scale': self.scaler.scale_
        }
        
        return results
    
    def identify_top_contributors(
        self,
        components_df: pd.DataFrame,
        n_top: int = 3
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Identify top contributing features for each principal component
        
        Args:
            components_df: DataFrame with component loadings
            n_top: Number of top contributors to identify
            
        Returns:
            Dictionary mapping component to top contributors
        """
        top_contributors = {}
        
        for pc in components_df.columns:
            # Get absolute loadings
            abs_loadings = components_df[pc].abs().sort_values(ascending=False)
            
            # Get top contributors with their actual loading values
            top_features = []
            for feature in abs_loadings.head(n_top).index:
                loading = components_df.loc[feature, pc]
                top_features.append((feature, loading))
                
            top_contributors[pc] = top_features
            
        return top_contributors
    
    def calculate_reconstruction_error(
        self,
        X_scaled: pd.DataFrame,
        pca_results: Dict
    ) -> pd.DataFrame:
        """
        Calculate reconstruction error for anomaly detection
        
        Args:
            X_scaled: Original scaled data
            pca_results: PCA results dictionary
            
        Returns:
            DataFrame with reconstruction errors
        """
        # Reconstruct data
        components = pca_results['components'].values
        transformed = pca_results['transformed_data'].values
        X_reconstructed = transformed @ components.T
        
        # Calculate errors
        reconstruction_error = np.sum((X_scaled.values - X_reconstructed) ** 2, axis=1)
        
        # Create error DataFrame
        error_df = pd.DataFrame({
            'reconstruction_error': reconstruction_error,
            'index': X_scaled.index
        })
        
        # Add percentile information
        error_df['error_percentile'] = error_df['reconstruction_error'].rank(pct=True)
        
        return error_df
    
    def detect_anomalies(
        self,
        error_df: pd.DataFrame,
        threshold_percentile: float = 0.95
    ) -> pd.DataFrame:
        """
        Detect anomalies based on reconstruction error
        
        Args:
            error_df: DataFrame with reconstruction errors
            threshold_percentile: Percentile threshold for anomaly detection
            
        Returns:
            DataFrame with anomaly flags
        """
        threshold = error_df['reconstruction_error'].quantile(threshold_percentile)
        
        anomaly_df = error_df.copy()
        anomaly_df['is_anomaly'] = anomaly_df['reconstruction_error'] > threshold
        anomaly_df['anomaly_score'] = (
            anomaly_df['reconstruction_error'] / threshold
        ).clip(upper=3.0)  # Cap at 3x threshold
        
        return anomaly_df
    
    def analyze_temporal_patterns(
        self,
        transformed_df: pd.DataFrame,
        original_df: pd.DataFrame
    ) -> Dict:
        """
        Analyze temporal patterns in principal components
        
        Args:
            transformed_df: PCA-transformed data
            original_df: Original data with timestamps
            
        Returns:
            Dictionary with temporal pattern analysis
        """
        # Add temporal features
        analysis_df = transformed_df.copy()
        analysis_df['timestamp'] = original_df['timestamp']
        analysis_df['hour'] = pd.to_datetime(analysis_df['timestamp']).dt.hour
        analysis_df['day_of_week'] = pd.to_datetime(analysis_df['timestamp']).dt.dayofweek
        analysis_df['month'] = pd.to_datetime(analysis_df['timestamp']).dt.month
        
        patterns = {}
        
        # Analyze each principal component
        for pc in [col for col in transformed_df.columns if col.startswith('PC')]:
            patterns[pc] = {
                'hourly_pattern': analysis_df.groupby('hour')[pc].mean().to_dict(),
                'daily_pattern': analysis_df.groupby('day_of_week')[pc].mean().to_dict(),
                'monthly_pattern': analysis_df.groupby('month')[pc].mean().to_dict(),
                'overall_stats': {
                    'mean': analysis_df[pc].mean(),
                    'std': analysis_df[pc].std(),
                    'min': analysis_df[pc].min(),
                    'max': analysis_df[pc].max()
                }
            }
            
        return patterns
    
    def generate_pca_report(
        self,
        pca_results: Dict,
        top_contributors: Dict[str, List[Tuple[str, float]]],
        anomaly_summary: Optional[Dict] = None
    ) -> str:
        """
        Generate a comprehensive PCA analysis report
        
        Args:
            pca_results: PCA results dictionary
            top_contributors: Top contributing features per component
            anomaly_summary: Optional anomaly detection summary
            
        Returns:
            Formatted report string
        """
        report = "PRINCIPAL COMPONENT ANALYSIS REPORT\n"
        report += "=" * 50 + "\n\n"
        
        # Variance explained
        report += "Variance Explained by Components:\n"
        report += "-" * 30 + "\n"
        
        for i, (var_ratio, cum_var) in enumerate(zip(
            pca_results['explained_variance_ratio'],
            pca_results['cumulative_variance_ratio']
        )):
            report += f"PC{i+1}: {var_ratio:.1%} (Cumulative: {cum_var:.1%})\n"
            
        report += f"\nTotal components: {pca_results['n_components']}\n"
        report += f"Total variance explained: {pca_results['cumulative_variance_ratio'][-1]:.1%}\n\n"
        
        # Component interpretation
        report += "Component Interpretation:\n"
        report += "-" * 30 + "\n"
        
        for pc, contributors in top_contributors.items():
            report += f"\n{pc} - Primary factors:\n"
            for feature, loading in contributors:
                direction = "positive" if loading > 0 else "negative"
                report += f"  • {feature}: {loading:+.3f} ({direction} contribution)\n"
                
        # Feature importance
        report += "\nFeature Importance Summary:\n"
        report += "-" * 30 + "\n"
        
        # Calculate overall feature importance
        components = pca_results['components']
        variance_ratios = pca_results['explained_variance_ratio']
        
        feature_importance = {}
        for feature in components.index:
            importance = sum(
                abs(components.loc[feature, f'PC{i+1}']) * variance_ratios[i]
                for i in range(len(variance_ratios))
            )
            feature_importance[feature] = importance
            
        # Sort by importance
        sorted_features = sorted(
            feature_importance.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        for feature, importance in sorted_features:
            report += f"{feature}: {importance:.3f}\n"
            
        # Anomaly summary if provided
        if anomaly_summary:
            report += f"\nAnomaly Detection Summary:\n"
            report += "-" * 30 + "\n"
            report += f"Total anomalies detected: {anomaly_summary.get('total_anomalies', 0)}\n"
            report += f"Anomaly rate: {anomaly_summary.get('anomaly_rate', 0):.1%}\n"
            
        return report
    
    def create_biplot_data(
        self,
        pca_results: Dict,
        pc_x: int = 1,
        pc_y: int = 2,
        scale_factor: float = 3.0
    ) -> Dict:
        """
        Prepare data for PCA biplot visualization
        
        Args:
            pca_results: PCA results dictionary
            pc_x: Principal component for x-axis (1-indexed)
            pc_y: Principal component for y-axis (1-indexed)
            scale_factor: Scaling factor for feature vectors
            
        Returns:
            Dictionary with biplot data
        """
        # Get scores (transformed data)
        scores = pca_results['transformed_data']
        
        # Get loadings (components)
        loadings = pca_results['components']
        
        # Scale loadings for visualization
        scaled_loadings = loadings * scale_factor
        
        biplot_data = {
            'scores': {
                'x': scores[f'PC{pc_x}'].values,
                'y': scores[f'PC{pc_y}'].values
            },
            'loadings': {
                'features': list(loadings.index),
                'x': scaled_loadings[f'PC{pc_x}'].values,
                'y': scaled_loadings[f'PC{pc_y}'].values
            },
            'variance_explained': {
                f'PC{pc_x}': pca_results['explained_variance_ratio'][pc_x-1],
                f'PC{pc_y}': pca_results['explained_variance_ratio'][pc_y-1]
            }
        }
        
        return biplot_data