import pandas as pd
from pathlib import Path
from src.utils.logger import get_logger

logger = get_logger(__name__)

class StatisticsEngine:
    def __init__(self, input_path="data/processed/analytics_data.parquet"):
        self.input_path = Path(input_path)
        
    def load_data(self):
        if not self.input_path.exists():
            logger.warning(f"Input path {self.input_path} does not exist.")
            return pd.DataFrame()
        return pd.read_parquet(self.input_path)
        
    def compute_statistics(self, df):
        """
        Computes aggregate statistics per symbol.
        """
        if df.empty:
            return pd.DataFrame()
            
        logger.info("Computing statistics...")
        
        stats_list = []
        
        for symbol, group in df.groupby('symbol'):
            stats = {
                'symbol': symbol,
                'start_date': group['timestamp'].min(),
                'end_date': group['timestamp'].max(),
                'mean_price': group['close'].mean(),
                'median_price': group['close'].median(),
                'min_price': group['close'].min(),
                'max_price': group['close'].max(),
                'std_dev_price': group['close'].std(),
                'avg_daily_return': group['daily_return'].mean(),
                'volatility_avg': group['volatility_7d'].mean()
            }
            stats_list.append(stats)
            
        stats_df = pd.DataFrame(stats_list)
        logger.info("Statistics computation completed.")
        return stats_df

    def run(self):
        df = self.load_data()
        if not df.empty:
            stats_df = self.compute_statistics(df)
            print("\n=== Summary Statistics ===")
            print(stats_df.to_string())
            return stats_df
        else:
            logger.warning("No data for statistics.")
            return pd.DataFrame()

if __name__ == "__main__":
    engine = StatisticsEngine()
    engine.run()
