"""
Multivariate Correlation Analysis Service
Implements Pearson and Spearman correlation calculations for weather parameters
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Literal
from scipy import stats
import psycopg2
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class CorrelationAnalysisService:
    """Service for computing multivariate correlations in weather data"""
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize the correlation analysis service
        
        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        
    def get_db_connection(self):
        """Create and return a database connection"""
        return psycopg2.connect(**self.db_config)
    
    def load_weather_data(
        self, 
        start_date: datetime,
        end_date: datetime,
        station_id: Optional[str] = None,
        parameters: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Load weather data for correlation analysis
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            station_id: Optional specific station ID
            parameters: Optional list of parameters to include
            
        Returns:
            DataFrame with weather data
        """
        if parameters is None:
            parameters = ['temperature', 'humidity', 'wind_speed', 
                         'wind_direction', 'radiation', 'precipitation']
        
        columns = ['timestamp', 'station_id'] + parameters
        query = f"""
        SELECT {', '.join(columns)}
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
            
        return df
    
    def calculate_correlations(
        self,
        df: pd.DataFrame,
        method: Literal['pearson', 'spearman', 'both'] = 'both',
        min_observations: int = 30
    ) -> Dict[str, pd.DataFrame]:
        """
        Calculate correlation matrices using specified methods
        
        Args:
            df: DataFrame with weather data
            method: Correlation method(s) to use
            min_observations: Minimum observations required for valid correlation
            
        Returns:
            Dictionary with correlation matrices
        """
        # Select only numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        numeric_cols = [col for col in numeric_cols if col not in ['station_id']]
        
        # Remove columns with insufficient data
        valid_cols = []
        for col in numeric_cols:
            non_null_count = df[col].notna().sum()
            if non_null_count >= min_observations:
                valid_cols.append(col)
            else:
                logger.warning(f"Excluding {col} - only {non_null_count} observations")
        
        if len(valid_cols) < 2:
            raise ValueError("Insufficient data for correlation analysis")
        
        # Prepare data
        analysis_df = df[valid_cols].copy()
        
        results = {}
        
        if method in ['pearson', 'both']:
            # Pearson correlation (linear relationships)
            pearson_corr = analysis_df.corr(method='pearson')
            results['pearson'] = pearson_corr
            
            # Calculate p-values for Pearson
            pearson_pvals = self._calculate_pvalues(analysis_df, method='pearson')
            results['pearson_pvalues'] = pearson_pvals
            
        if method in ['spearman', 'both']:
            # Spearman correlation (monotonic relationships)
            spearman_corr = analysis_df.corr(method='spearman')
            results['spearman'] = spearman_corr
            
            # Calculate p-values for Spearman
            spearman_pvals = self._calculate_pvalues(analysis_df, method='spearman')
            results['spearman_pvalues'] = spearman_pvals
            
        return results
    
    def _calculate_pvalues(
        self, 
        df: pd.DataFrame, 
        method: Literal['pearson', 'spearman']
    ) -> pd.DataFrame:
        """
        Calculate p-values for correlation coefficients
        
        Args:
            df: DataFrame with data
            method: Correlation method
            
        Returns:
            DataFrame with p-values
        """
        cols = df.columns
        n_cols = len(cols)
        pvals = np.zeros((n_cols, n_cols))
        
        for i in range(n_cols):
            for j in range(n_cols):
                if i == j:
                    pvals[i, j] = 0.0
                else:
                    # Remove NaN values pairwise
                    mask = df[[cols[i], cols[j]]].notna().all(axis=1)
                    x = df.loc[mask, cols[i]]
                    y = df.loc[mask, cols[j]]
                    
                    if len(x) < 3:
                        pvals[i, j] = 1.0
                    else:
                        if method == 'pearson':
                            _, p = stats.pearsonr(x, y)
                        else:
                            _, p = stats.spearmanr(x, y)
                        pvals[i, j] = p
                        
        return pd.DataFrame(pvals, index=cols, columns=cols)
    
    def identify_strong_correlations(
        self,
        correlation_matrix: pd.DataFrame,
        pvalue_matrix: Optional[pd.DataFrame] = None,
        threshold: float = 0.7,
        pvalue_threshold: float = 0.05
    ) -> List[Tuple[str, str, float, Optional[float]]]:
        """
        Identify strong correlations above threshold
        
        Args:
            correlation_matrix: Correlation coefficient matrix
            pvalue_matrix: Optional p-value matrix
            threshold: Minimum absolute correlation to report
            pvalue_threshold: Maximum p-value for significance
            
        Returns:
            List of tuples (var1, var2, correlation, p-value)
        """
        strong_correlations = []
        
        # Get upper triangle indices to avoid duplicates
        for i in range(len(correlation_matrix.columns)):
            for j in range(i+1, len(correlation_matrix.columns)):
                var1 = correlation_matrix.columns[i]
                var2 = correlation_matrix.columns[j]
                corr = correlation_matrix.iloc[i, j]
                
                if abs(corr) >= threshold:
                    pval = None
                    if pvalue_matrix is not None:
                        pval = pvalue_matrix.iloc[i, j]
                        if pval > pvalue_threshold:
                            continue
                    
                    strong_correlations.append((var1, var2, corr, pval))
        
        # Sort by absolute correlation strength
        strong_correlations.sort(key=lambda x: abs(x[2]), reverse=True)
        
        return strong_correlations
    
    def analyze_temporal_stability(
        self,
        start_date: datetime,
        end_date: datetime,
        window_days: int = 30,
        step_days: int = 7,
        station_id: Optional[str] = None,
        parameters: Optional[List[str]] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Analyze how correlations change over time using rolling windows
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            window_days: Size of rolling window in days
            step_days: Step size between windows
            station_id: Optional specific station
            parameters: Parameters to analyze
            
        Returns:
            Dictionary with temporal correlation results
        """
        if parameters is None:
            parameters = ['temperature', 'humidity', 'wind_speed', 'radiation']
            
        results = {
            'windows': [],
            'correlations': {}
        }
        
        # Initialize correlation tracking
        for i, param1 in enumerate(parameters):
            for j, param2 in enumerate(parameters):
                if i < j:
                    key = f"{param1}_vs_{param2}"
                    results['correlations'][key] = {
                        'pearson': [],
                        'spearman': []
                    }
        
        # Sliding window analysis
        current_start = start_date
        while current_start + timedelta(days=window_days) <= end_date:
            current_end = current_start + timedelta(days=window_days)
            
            # Load data for window
            df = self.load_weather_data(
                current_start, current_end, station_id, parameters
            )
            
            if len(df) >= 30:  # Minimum observations
                try:
                    corr_results = self.calculate_correlations(df, method='both')
                    
                    results['windows'].append({
                        'start': current_start,
                        'end': current_end,
                        'observations': len(df)
                    })
                    
                    # Extract correlations
                    for i, param1 in enumerate(parameters):
                        for j, param2 in enumerate(parameters):
                            if i < j and param1 in corr_results['pearson'].columns and param2 in corr_results['pearson'].columns:
                                key = f"{param1}_vs_{param2}"
                                pearson_val = corr_results['pearson'].loc[param1, param2]
                                spearman_val = corr_results['spearman'].loc[param1, param2]
                                
                                results['correlations'][key]['pearson'].append(pearson_val)
                                results['correlations'][key]['spearman'].append(spearman_val)
                                
                except Exception as e:
                    logger.warning(f"Failed to calculate correlations for window {current_start} to {current_end}: {e}")
            
            current_start += timedelta(days=step_days)
        
        return results
    
    def generate_correlation_report(
        self,
        correlation_results: Dict[str, pd.DataFrame],
        strong_correlations: List[Tuple[str, str, float, Optional[float]]]
    ) -> str:
        """
        Generate a text report of correlation analysis results
        
        Args:
            correlation_results: Dictionary with correlation matrices
            strong_correlations: List of strong correlations
            
        Returns:
            Formatted report string
        """
        report = "WEATHER PARAMETER CORRELATION ANALYSIS REPORT\n"
        report += "=" * 50 + "\n\n"
        
        # Summary statistics
        if 'pearson' in correlation_results:
            pearson_flat = correlation_results['pearson'].values[np.triu_indices_from(
                correlation_results['pearson'].values, k=1
            )]
            report += f"Pearson Correlation Summary:\n"
            report += f"  Mean absolute correlation: {np.mean(np.abs(pearson_flat)):.3f}\n"
            report += f"  Strongest correlation: {np.max(np.abs(pearson_flat)):.3f}\n\n"
            
        if 'spearman' in correlation_results:
            spearman_flat = correlation_results['spearman'].values[np.triu_indices_from(
                correlation_results['spearman'].values, k=1
            )]
            report += f"Spearman Correlation Summary:\n"
            report += f"  Mean absolute correlation: {np.mean(np.abs(spearman_flat)):.3f}\n"
            report += f"  Strongest correlation: {np.max(np.abs(spearman_flat)):.3f}\n\n"
        
        # Strong correlations
        report += "Strong Correlations Identified:\n"
        report += "-" * 30 + "\n"
        
        if strong_correlations:
            for var1, var2, corr, pval in strong_correlations:
                report += f"{var1} <-> {var2}: {corr:.3f}"
                if pval is not None:
                    report += f" (p={pval:.4f})"
                report += "\n"
                
                # Interpret correlation
                if abs(corr) >= 0.9:
                    strength = "Very strong"
                elif abs(corr) >= 0.7:
                    strength = "Strong"
                elif abs(corr) >= 0.5:
                    strength = "Moderate"
                else:
                    strength = "Weak"
                    
                direction = "positive" if corr > 0 else "negative"
                report += f"  -> {strength} {direction} relationship\n\n"
        else:
            report += "No strong correlations found above threshold.\n"
            
        return report