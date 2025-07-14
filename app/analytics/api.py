"""
API endpoints for analytics services
Provides REST API access to correlation and PCA analysis
"""

import os
import json
from datetime import datetime
from typing import Dict, Optional, List
import pandas as pd
import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS

from .correlation_service import CorrelationAnalysisService
from .pca_service import PCAAnalysisService

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'weather_db'),
    'user': os.getenv('DB_USER', 'weather_user'),
    'password': os.getenv('DB_PASSWORD', 'weather_password')
}

# Initialize services
correlation_service = CorrelationAnalysisService(DB_CONFIG)
pca_service = PCAAnalysisService(DB_CONFIG)


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for numpy types"""
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.float64, np.float32)):
            return float(obj)
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict('records')
        return super().default(obj)


@app.route('/api/analytics/correlation', methods=['POST'])
def calculate_correlation():
    """
    Calculate correlation analysis
    
    Request body:
    {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "station_id": "256",  # optional
        "parameters": ["temperature", "humidity"],  # optional
        "method": "both",  # "pearson", "spearman", or "both"
        "threshold": 0.7
    }
    """
    try:
        data = request.get_json()
        
        # Parse dates
        start_date = datetime.fromisoformat(data['start_date'])
        end_date = datetime.fromisoformat(data['end_date'])
        
        # Load data
        df = correlation_service.load_weather_data(
            start_date=start_date,
            end_date=end_date,
            station_id=data.get('station_id'),
            parameters=data.get('parameters')
        )
        
        # Calculate correlations
        results = correlation_service.calculate_correlations(
            df=df,
            method=data.get('method', 'both')
        )
        
        # Identify strong correlations
        strong_correlations = []
        threshold = data.get('threshold', 0.7)
        
        for method in results:
            if method.endswith('_pvalues'):
                continue
                
            pval_matrix = results.get(f"{method}_pvalues")
            strong_corr = correlation_service.identify_strong_correlations(
                correlation_matrix=results[method],
                pvalue_matrix=pval_matrix,
                threshold=threshold
            )
            
            for var1, var2, corr, pval in strong_corr:
                strong_correlations.append({
                    'method': method,
                    'variable1': var1,
                    'variable2': var2,
                    'correlation': float(corr),
                    'p_value': float(pval) if pval is not None else None
                })
        
        # Prepare response
        response = {
            'success': True,
            'data': {
                'observations': len(df),
                'correlations': {
                    method: results[method].to_dict() 
                    for method in results 
                    if not method.endswith('_pvalues')
                },
                'strong_correlations': strong_correlations,
                'parameters': list(results.get('pearson', results.get('spearman')).columns)
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/analytics/correlation/temporal', methods=['POST'])
def calculate_temporal_correlation():
    """
    Calculate temporal stability of correlations
    
    Request body:
    {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "window_days": 30,
        "step_days": 7,
        "station_id": "256",  # optional
        "parameters": ["temperature", "humidity"]  # optional
    }
    """
    try:
        data = request.get_json()
        
        # Parse dates
        start_date = datetime.fromisoformat(data['start_date'])
        end_date = datetime.fromisoformat(data['end_date'])
        
        # Analyze temporal stability
        results = correlation_service.analyze_temporal_stability(
            start_date=start_date,
            end_date=end_date,
            window_days=data.get('window_days', 30),
            step_days=data.get('step_days', 7),
            station_id=data.get('station_id'),
            parameters=data.get('parameters')
        )
        
        # Format windows for JSON
        windows = []
        for window in results['windows']:
            windows.append({
                'start': window['start'].isoformat(),
                'end': window['end'].isoformat(),
                'observations': window['observations']
            })
        
        response = {
            'success': True,
            'data': {
                'windows': windows,
                'correlations': results['correlations']
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/analytics/pca', methods=['POST'])
def calculate_pca():
    """
    Calculate PCA analysis
    
    Request body:
    {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "station_id": "256",  # optional
        "parameters": ["temperature", "humidity"],  # optional
        "n_components": 3,  # optional, auto if not specified
        "variance_threshold": 0.95,  # optional
        "aggregation": "hourly"  # or "daily"
    }
    """
    try:
        data = request.get_json()
        
        # Parse dates
        start_date = datetime.fromisoformat(data['start_date'])
        end_date = datetime.fromisoformat(data['end_date'])
        
        # Prepare data
        X_scaled, original_df, feature_names = pca_service.prepare_data_for_pca(
            start_date=start_date,
            end_date=end_date,
            station_id=data.get('station_id'),
            parameters=data.get('parameters'),
            aggregation=data.get('aggregation', 'hourly')
        )
        
        # Perform PCA
        pca_results = pca_service.perform_pca(
            X_scaled=X_scaled,
            n_components=data.get('n_components'),
            variance_threshold=data.get('variance_threshold', 0.95)
        )
        
        # Identify top contributors
        top_contributors = pca_service.identify_top_contributors(
            components_df=pca_results['components'],
            n_top=3
        )
        
        # Calculate reconstruction error for anomaly detection
        error_df = pca_service.calculate_reconstruction_error(X_scaled, pca_results)
        anomaly_df = pca_service.detect_anomalies(error_df)
        
        # Prepare response
        response = {
            'success': True,
            'data': {
                'n_components': int(pca_results['n_components']),
                'explained_variance_ratio': pca_results['explained_variance_ratio'].tolist(),
                'cumulative_variance_ratio': pca_results['cumulative_variance_ratio'].tolist(),
                'components': pca_results['components'].to_dict(),
                'top_contributors': {
                    pc: [(feat, float(load)) for feat, load in contribs]
                    for pc, contribs in top_contributors.items()
                },
                'anomalies': {
                    'total': int(anomaly_df['is_anomaly'].sum()),
                    'rate': float(anomaly_df['is_anomaly'].mean()),
                    'threshold_percentile': 0.95
                },
                'observations': len(X_scaled),
                'features': feature_names
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/analytics/pca/biplot', methods=['POST'])
def get_pca_biplot_data():
    """
    Get PCA biplot data for visualization
    
    Request body:
    {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "station_id": "256",  # optional
        "pc_x": 1,
        "pc_y": 2,
        "scale_factor": 3.0
    }
    """
    try:
        data = request.get_json()
        
        # Parse dates
        start_date = datetime.fromisoformat(data['start_date'])
        end_date = datetime.fromisoformat(data['end_date'])
        
        # Prepare data and perform PCA
        X_scaled, original_df, feature_names = pca_service.prepare_data_for_pca(
            start_date=start_date,
            end_date=end_date,
            station_id=data.get('station_id'),
            parameters=data.get('parameters')
        )
        
        pca_results = pca_service.perform_pca(X_scaled)
        
        # Create biplot data
        biplot_data = pca_service.create_biplot_data(
            pca_results=pca_results,
            pc_x=data.get('pc_x', 1),
            pc_y=data.get('pc_y', 2),
            scale_factor=data.get('scale_factor', 3.0)
        )
        
        # Add timestamps for scores
        biplot_data['scores']['timestamps'] = original_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M').tolist()
        
        response = {
            'success': True,
            'data': biplot_data
        }
        
        return json.dumps(response, cls=NumpyEncoder), 200, {'Content-Type': 'application/json'}
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/analytics/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'services': {
            'correlation': 'available',
            'pca': 'available'
        }
    }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)