import requests
import os
import json
import time
import datetime
from pathlib import Path
from src.utils.logger import get_logger

logger = get_logger(__name__)

class AlphaVantageClient:
    def __init__(self, api_key, base_url="https://www.alphavantage.co/query"):
        self.api_key = api_key
        self.base_url = base_url
    
    def fetch_data(self, symbol, function="TIME_SERIES_INTRADAY", interval="5min", outputsize="compact"):
        """
        Fetches data from Alpha Vantage API.
        Handles rate limits and retries.
        """
        params = {
            "function": function,
            "symbol": symbol,
            "apikey": self.api_key,
            "outputsize": outputsize,
            "datatype": "json"
        }
        if function == "TIME_SERIES_INTRADAY":
            params["interval"] = interval
        
        max_retries = 5
        backoff_factor = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching data for {symbol}, attempt {attempt + 1}")
                response = requests.get(self.base_url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    if "Note" in data:
                        # API limit reached
                        logger.warning(f"API limit reached for {symbol}: {data['Note']}")
                        if attempt < max_retries - 1:
                            sleep_time = backoff_factor ** attempt
                            logger.info(f"Retrying in {sleep_time} seconds...")
                            time.sleep(sleep_time)
                            continue
                        else:
                            logger.error(f"Max retries reached for {symbol} due to API limits.")
                            return None
                    
                    if "Error Message" in data:
                        logger.error(f"API Error for {symbol}: {data['Error Message']}")
                        return None
                        
                    return data
                else:
                    logger.error(f"HTTP Error {response.status_code} for {symbol}")
                    if attempt < max_retries - 1:
                        time.sleep(backoff_factor ** attempt)
                        continue
                    return None
            except Exception as e:
                logger.error(f"Exception during fetch for {symbol}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(backoff_factor ** attempt)
                    continue
                return None
        return None

    def save_raw_data(self, data, symbol, base_path="data/raw"):
        """
        Saves raw data to partitioned directory structure.
        Format: base_path/alpha_vantage/symbol=<SYMBOL>/date=<YYYY-MM-DD>/data.json
        """
        if not data:
            logger.warning(f"No data to save for {symbol}")
            return

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Partitioned path
        save_dir = Path(base_path) / "alpha_vantage" / f"symbol={symbol}" / f"date={today}"
        save_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = save_dir / "data.json"
        
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Successfully saved raw data for {symbol} to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save raw data for {symbol}: {e}")

if __name__ == "__main__":
    # Test execution
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if api_key:
        client = AlphaVantageClient(api_key)
        data = client.fetch_data("IBM") # Test with IBM
        client.save_raw_data(data, "IBM")
    else:
        print("API Key not found in environment variables.")
