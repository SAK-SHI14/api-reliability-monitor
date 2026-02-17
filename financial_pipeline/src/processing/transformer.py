import pandas as pd
from pathlib import Path
from src.utils.logger import get_logger

logger = get_logger(__name__)

class DataTransformer:
    def __init__(self, input_path="data/processed/cleaned_data.parquet", output_path="data/processed/analytics_data.parquet"):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        
    def load_clean_data(self):
        if not self.input_path.exists():
            logger.warning(f"Input path {self.input_path} does not exist.")
            return pd.DataFrame()
        return pd.read_parquet(self.input_path)
        
    def transform_data(self, df):
        if df.empty:
            return df
            
        logger.info("Starting data transformation...")
        
        # Ensure data is sorted for time-series calculations
        df = df.sort_values(by=['symbol', 'timestamp'])
        
        # 1. Daily Returns
        df['daily_return'] = df.groupby('symbol')['close'].pct_change()
        
        # 2. Rolling Means (Simple Moving Averages)
        windows = [7, 14, 30]
        for window in windows:
            df[f'sma_{window}'] = df.groupby('symbol')['close'].transform(lambda x: x.rolling(window=window).mean())
            
        # 3. Rolling Volatility (Standard Deviation)
        # Using 7-day window for volatility by default
        df['volatility_7d'] = df.groupby('symbol')['close'].transform(lambda x: x.rolling(window=7).std())
        
        # Handle NaN values created by rolling/shifting
        # We can drop the initial rows or fill them. Dropping is safer for strict analytics.
        # But for pipeline continuity, we might want to keep them with NaNs or fill.
        # Let's drop rows where we can't calculate the largest window (30) to ensure clean data for models, 
        # BUT for visualization we might want to see the early data.
        # Decision: Keep NaNs, let downstream handle it (e.g. dropna() before plotting if needed).
        
        logger.info(f"Data transformation completed. Columns added: daily_return, sma_*, volatility_*")
        return df

    def run(self):
        df = self.load_clean_data()
        if not df.empty:
            transformed_df = self.transform_data(df)
            
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                transformed_df.to_parquet(self.output_path, index=False)
                logger.info(f"Saved analytics data to {self.output_path}")
            except Exception as e:
                logger.error(f"Failed to save analytics data: {e}")
        else:
            logger.warning("No data to transform.")

if __name__ == "__main__":
    transformer = DataTransformer()
    transformer.run()
