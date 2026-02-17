import pandas as pd
import json
import os
from pathlib import Path
from src.utils.logger import get_logger

logger = get_logger(__name__)

class DataCleaner:
    def __init__(self, raw_path="data/raw", processed_path="data/processed/cleaned_data.parquet"):
        self.raw_path = Path(raw_path)
        self.processed_path = Path(processed_path)
        
    def load_raw_data(self):
        """
        Walks through the raw data directory and loads all JSON files.
        Returns a combined DataFrame.
        """
        all_data = []
        
        # Structure: raw/alpha_vantage/symbol=<SYMBOL>/date=<YYYY-MM-DD>/data.json
        # We need to extract Symbol and Date from path or content.
        # content has "Meta Data" and "Time Series (Daily)".
        
        if not self.raw_path.exists():
            logger.warning(f"Raw path {self.raw_path} does not exist.")
            return pd.DataFrame()

        for file_path in self.raw_path.rglob("*.json"):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                # Parsing Alpha Vantage format (Daily or Intraday)
                # "Meta Data": { "2. Symbol": "IBM", ... }
                # "Time Series (Daily)": ... or "Time Series (5min)": ...
                
                if "Meta Data" not in data:
                    logger.warning(f"Skipping Invalid JSON format in {file_path}")
                    continue
                
                # Find the key that starts with "Time Series"
                time_series_key = next((k for k in data.keys() if k.startswith("Time Series")), None)
                
                if not time_series_key:
                    logger.warning(f"No Time Series data found in {file_path}")
                    continue
                    
                symbol = data["Meta Data"]["2. Symbol"]
                time_series = data[time_series_key]
                
                for date_str, values in time_series.items():
                    record = {
                        "timestamp": date_str,
                        "symbol": symbol,
                        "open": float(values.get("1. open", 0)),
                        "high": float(values.get("2. high", 0)),
                        "low": float(values.get("3. low", 0)),
                        "close": float(values.get("4. close", 0)),
                        "volume": int(values.get("5. volume", 0))
                    }
                    all_data.append(record)
                    
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                
        if not all_data:
            logger.warning("No data found in raw directory.")
            return pd.DataFrame()
            
        return pd.DataFrame(all_data)

    def clean_data(self, df):
        """
        Performs data cleaning:
        - Type conversion
        - Handling missing values
        - Removing duplicates
        - Sorting
        """
        if df.empty:
            return df
            
        logger.info("Starting data cleaning...")
        
        # 1. Type Conversion
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # 2. Sort by Symbol and Date
        df = df.sort_values(by=['symbol', 'timestamp']).reset_index(drop=True)
        
        # 3. Remove Duplicates
        initial_count = len(df)
        df = df.drop_duplicates(subset=['symbol', 'timestamp'], keep='last')
        if len(df) < initial_count:
            logger.info(f"Removed {initial_count - len(df)} duplicate records.")
            
        # 4. Handle Missing Values
        # For stock data, forward fill is often appropriate for missing prices (carry forward last known price)
        # However, if we have gaps in 'trading days', we might want to respect that.
        # Here we just check for NaNs in the data we have.
        if df.isnull().sum().sum() > 0:
            logger.warning(f"Found missing values. Filling with forward fill.")
            df = df.groupby('symbol').ffill().bfill() # ffill then bfill logic
            
        logger.info(f"Data cleaning completed. Shape: {df.shape}")
        return df

    def run(self):
        """
        Main execution method.
        """
        df = self.load_raw_data()
        if not df.empty:
            cleaned_df = self.clean_data(df)
            
            # Ensure output directory exists
            self.processed_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                cleaned_df.to_parquet(self.processed_path, index=False)
                logger.info(f"Saved cleaned data to {self.processed_path}")
            except Exception as e:
                logger.error(f"Failed to save cleaned data: {e}")
        else:
            logger.warning("No data to clean.")

if __name__ == "__main__":
    cleaner = DataCleaner()
    cleaner.run()
