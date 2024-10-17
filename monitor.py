# Imports
import logging
from logging.handlers import RotatingFileHandler
import os

# Logging Setup
logger = logging.getLogger('Auto_Trader')
logger.setLevel(logging.DEBUG)  # Set the logging level for the logger
# Rotating file handler (file size limit of 1 MB, keeps 5 backup files)
file_handler = RotatingFileHandler('app.log', maxBytes=1_000_000, backupCount=5)
# Create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Access the API key from environment variables
API_KEY = os.getenv('API_KEY')

if API_KEY is None:
    raise ValueError("API_KEY environment variable is not set")

def check_make_adjustments():
    # Start Procedure
    logger.info("<<<<<<<<<<<<<<<<START>>>>>>>>>>>>>>>>>")
    logger.info("Got API key : " + API_KEY)

    # Login
    logger.info("Logged in")

    # Check positions
    logger.info("Positions:")

    # Evaluate poistions and determine adjustments
    logger.info("Conditions evaluated")

    # Evaluate Margin requirement and available margin/funds
    logger.info("Adjustments mapped")

    # Apply adjustments, if required
    logger.info("Adjustments applied")

    # Exit
    logger.info("<<<<<<<<<<<<<<<<END>>>>>>>>>>>>>>>>>")

if __name__ == "__main__":
    check_make_adjustments()