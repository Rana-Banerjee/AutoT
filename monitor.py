# Imports
import logging
from logging.handlers import RotatingFileHandler

# Logging Setup
logger = logging.getLogger('Auto_Trader')
logger.setLevel(logging.DEBUG)  # Set the logging level for the logger
# Rotating file handler (file size limit of 1 MB, keeps 5 backup files)
file_handler = RotatingFileHandler('app.log', maxBytes=1_000_000, backupCount=5)
# Create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Start Procedure
logger.info("<<<<<<<<<<<<<<<<START>>>>>>>>>>>>>>>>>")

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