import logging
import logging.config
import yaml
import os

def setup_logging(config_path='config/logging_config.yaml'):
    """
    Setup logging configuration
    """
    # Resolve path relative to the project root (assuming this file is in src/utils)
    # src/utils/../../ -> project root
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    full_config_path = os.path.join(base_dir, config_path)
    
    if os.path.exists(full_config_path):
        with open(full_config_path, 'rt') as f:
            try:
                config = yaml.safe_load(f.read())
                # Ensure log directory exists
                log_file = config.get('handlers', {}).get('file', {}).get('filename')
                if log_file:
                    # Log file should also be absolute or relative to CWD? 
                    # Usually relative to where script is run is fine for logs, but let's make it relative to project root for consistency
                    if not os.path.isabs(log_file):
                        log_file = os.path.join(base_dir, log_file)
                        config['handlers']['file']['filename'] = log_file
                        
                    log_dir = os.path.dirname(log_file)
                    if log_dir and not os.path.exists(log_dir):
                        os.makedirs(log_dir)
                
                logging.config.dictConfig(config)
            except Exception as e:
                print(f"Error in Logging Configuration. Using default configs. Error: {e}")
                logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.INFO)
        print(f"Failed to load configuration file at {full_config_path}. Using default configs")

def get_logger(name):
    return logging.getLogger(name)
