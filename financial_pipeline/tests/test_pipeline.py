import pytest
import sys
import os
import pandas as pd

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from src.processing.cleaner import DataCleaner
from src.processing.transformer import DataTransformer
from src.analysis.statistics_engine import StatisticsEngine

def test_cleaner_initialization():
    cleaner = DataCleaner()
    assert cleaner.raw_path is not None
    assert cleaner.processed_path is not None

def test_transformer_logic():
    # Create dummy data
    data = {
        'symbol': ['TEST', 'TEST', 'TEST', 'TEST', 'TEST', 'TEST', 'TEST', 'TEST'],
        'timestamp': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05', '2023-01-06', '2023-01-07', '2023-01-08']),
        'close': [100, 101, 102, 103, 104, 105, 106, 107]
    }
    df = pd.DataFrame(data)
    
    transformer = DataTransformer()
    transformed_df = transformer.transform_data(df)
    
    assert 'daily_return' in transformed_df.columns
    assert 'sma_7' in transformed_df.columns
    assert 'volatility_7d' in transformed_df.columns
    
    # Check simple calculation
    # Daily return for first row is usually NaN or 0 depending on method, here pct_change gives NaN for first
    assert pd.isna(transformed_df.iloc[0]['daily_return'])
    assert transformed_df.iloc[1]['daily_return'] == (101-100)/100

def test_statistics_engine():
    data = {
        'symbol': ['TEST'],
        'timestamp': pd.to_datetime(['2023-01-01']),
        'close': [100],
        'daily_return': [0.01],
        'volatility_7d': [0.5]
    }
    df = pd.DataFrame(data)
    
    engine = StatisticsEngine()
    stats = engine.compute_statistics(df)
    
    assert not stats.empty
    assert stats.iloc[0]['symbol'] == 'TEST'
    assert stats.iloc[0]['mean_price'] == 100
