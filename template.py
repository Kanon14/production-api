import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s]: %(message)s:')


list_of_files = [
    "app/__init__.py",
    "app/agent.py",
    "app/cache.py",
    "app/config.py",
    "app/models.py",
    "app/monitoring.py",
    "app/security.py",
    "tests/test_security.py",
    "tests/test_cache.py",
    "tests/test_api.py",
    "main.py"
]

for filepath in list_of_files:
    filepath = Path(filepath)
    
    filedir, filename = os.path.split(filepath)
    
    if filedir != "":
        os.makedirs(filedir, exist_ok=True)
        logging.info(f"Creating directory: {filedir} for the file {filename}")
    
    if (not os.path.exists(filename)) or (os.path.getsize(filename) == 0):
        with open(filepath, "w") as f:
            pass
            logging.info(f"Creating empty file: {filename}")    
    else:
        logging.info(f"File already exists: {filename}")