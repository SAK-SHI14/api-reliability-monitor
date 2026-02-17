import os
import sys
import argparse
from dotenv import load_dotenv
import yaml

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.logger import setup_logging, get_logger
from src.ingestion.alpha_vantage_client import AlphaVantageClient
from src.processing.cleaner import DataCleaner
from src.processing.transformer import DataTransformer
from src.analysis.statistics_engine import StatisticsEngine

# Load Env
load_dotenv()
setup_logging()
logger = get_logger("main")

def load_config(config_relative_path="config/config.yaml"):
    # Resolve path relative to this script's directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, config_relative_path)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at: {config_path}")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def run_pipeline():
    logger.info("Starting Financial Data Pipeline...")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config = load_config()
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    
    if not api_key:
        logger.error("API Key not found. Please set ALPHA_VANTAGE_API_KEY in .env")
        return

    # Resolve Data Paths
    raw_path = os.path.join(base_dir, config['ingestion']['output_path'])
    processed_path = os.path.join(base_dir, config['processing']['processed_data_path'])
    analytics_path = os.path.join(base_dir, "data", "processed", "analytics_data.parquet")

    # Execution Mode
    mode = config.get('pipeline', {}).get('execution_mode', 'batch')
    poll_interval = config.get('pipeline', {}).get('poll_interval_seconds', 300)
    
    while True:
        try:
            # 1. Ingestion
            logger.info("--- Stage 1: Ingestion ---")
            client = AlphaVantageClient(api_key)
            symbols = config['ingestion']['symbols']
            interval = config['ingestion'].get('intraday_interval', '5min')
            function = config['ingestion'].get('interval', 'TIME_SERIES_INTRADAY')
            
            for symbol in symbols:
                try:
                    data = client.fetch_data(symbol, function=function, interval=interval)
                    if data:
                        client.save_raw_data(data, symbol, base_path=raw_path)
                except Exception as e:
                    logger.error(f"Failed ingestion for {symbol}: {e}")

            # 2. Cleaning
            logger.info("--- Stage 2: Cleaning ---")
            cleaner = DataCleaner(raw_path=raw_path, processed_path=processed_path)
            cleaner.run()

            # 3. Transformation
            logger.info("--- Stage 3: Transformation ---")
            transformer = DataTransformer(input_path=processed_path, output_path=analytics_path)
            transformer.run()

            # 4. Analysis
            logger.info("--- Stage 4: Analysis ---")
            stats_engine = StatisticsEngine(input_path=analytics_path)
            stats_engine.run()
            
            logger.info("Pipeline cycle completed.")
            
            if mode != 'continuous':
                break
                
            logger.info(f"Sleeping for {poll_interval} seconds...")
            import time
            time.sleep(poll_interval)
            
        except KeyboardInterrupt:
            logger.info("Pipeline stopped by user.")
            break
        except Exception as e:
            logger.error(f"Pipeline crashed: {e}")
            if mode != 'continuous':
                break
            import time
            time.sleep(poll_interval) # Wait before retry

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Financial Data Pipeline")
    parser.add_argument("--mode", type=str, default="all", help="Mode: all (default)")
    args = parser.parse_args()
    
    run_pipeline()
