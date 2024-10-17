# Imports
import logging
from logging.handlers import RotatingFileHandler
import os
import json
import requests
from api_helper import ShoonyaApiPy

# Logging Setup
logger = logging.getLogger('Auto_Trader')
logger.setLevel(logging.DEBUG)  # Set the logging level for the logger
# Rotating file handler (file size limit of 1 MB, keeps 5 backup files)
file_handler = RotatingFileHandler('logs/app.log', maxBytes=1_000_000, backupCount=5)
# Create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Access the API key from environment variables
API_KEY = os.getenv('API_KEY')

# Global variables
lot_size = 2
IC_Delta_Threshold=0.4
IF_Delta_Threshold=0.5
target=100
stop_loss=100
hedge_points=200

script_name = 'NIFTY NOV'

threshold = None
adj_leg=None

# Initialize the API
# api = ShoonyaApiPy()

if API_KEY is None:
    logger.info("API_KEY not set")
    raise ValueError("API_KEY environment variable is not set")

def check_make_adjustments():
    # Start Procedure
    logger.info("<<<<<<<<<<<<<<<<START>>>>>>>>>>>>>>>>>")
    # do_adjustment = False
    # extra_sell=False

    logger.info("Got API key : " + API_KEY)

    # Login
    # Login to the API
    # login_response = api.login(userid=user_id, password=password, twoFA=twoFA, vendor_code=vendor_code, api_secret=api_secret, imei=imei)   
    # if login_response['stat'] == 'Ok':
    #     print("Login successful!")
    # else:
    #     print(f"Login failed: {login_response['message']}")
    #     exit

    logger.info("Logged in")

    # Check positions
    logger.info("Positions:")
    # Fetch current positions
    # positions_response = api.get_positions()  # This function may vary based on the actual API implementation
    
    # if positions_response['stat'] == 'Ok':
    #     print("Current Positions:")
    #     for position in positions_response['data']:
    #         print(json.dumps(position, indent=4))
    # else:
    #     print(f"Error fetching positions: {positions_response['message']}")
    # # Get only active positions and identify, what to do when there is an extra sell?
    # Get Put Hedge: Strike, Entry, LTP, Delta?,  
    # Get Put Sell: Strike, Entry, LTP, Delta?, # Put with highest strike
    # Get Call Sell: Strike, Entry, LTP, Delta?, # Call with lowest strike
    # Get Call Hedge: Strike, Entry, LTP, Delta?, 
    # Get extra put sell, if more than one put sell then Put with lower strike: Strike, Entry, LTP, Delta?
    # Get extra call sell, if more than one call sell then Call with higher strike: Strike, Entry, LTP, Delta?
    # if extra_put_sell or extra_call_sell:
    #     extra_sell = True
    # Get current profits

    # Validate entries
    # If no_positions --> exit
    # Check All 4 legs retrieved
    # Check prices for all positions is valid
    # Call Strike Price is not less than Put Strike Price
    # Call_Hedge is not equal to or higher than call_strike, put_strike, call_hedge
    # Put_Hedge is not equal to or lower than call_strike, put_strike, put_hedge

    # Evaluate poistions and determine adjustments
    logger.info("Conditions evaluated")

    # Check stop_loss and targets
    # if curr_profits > target or curr_profits<stop_loss:
    #     exit trade

    # # Check whether its an IC or IF
    # if put_strike == call_strike:
    #     strategy = "IF"
    #     threshold = IF_Delta_Threshold
    # elif put_strike < call_strike:
    #     strategy = "IC"
    #     threshold = IC_Delta_Threshold
    # else:
    #     raise error and exit

    # Check for condition to exit extra sell
    # if extra_sell:


    # # Check Delta variation 
    # delta_base = (call_ltp+put_ltp)*threshold 
    # current_delta_diff = abs(call_ltp-put_ltp)
    # if current_delta_diff>delta_base:
    #     do_adjustment=True

    logger.info("Adjustments mapped")

    # Apply adjustments, if required
    # Evaluate Margin requirement and available margin/funds : 
    # ????

    # Iron Fly adjustments
    # if strategy='IF' and do_adjustment:
        # exit the profitable leg
        # Find the profitable leg,
        # if call_ltp-call_entry > put_ltp-put_entry:
        #     adj_leg = 'CALL'
        # elif call_ltp-call_entry < put_ltp-put_entry:
        #     adj_leg = 'PUT'
        # # Sell leg with lower ltp, or leg with max diff between entry and ltp values
        # if adj_leg=='CALL':
        #     Exit call and call_hedge
        # # Build new positions:
        # # Check the LTP of the non_profitable sell leg
        # Get Option Chain api
        # Start from strike price of the non_profitable leg
        # If the LTP of the corresponding Put/Call is higher than LTP of non-profitable leg:
        #     Convert to Iron Fly: Sell corresponding Put/Call at the same strike price
        
        # buy hedge at new_leg_strike_price +/- (non_profitable leg strike_price - non_profitable )
        # Start going Find Put/Call with the nearest matching ltp, strike in 00 till max strike of the non-profitable sell leg

    logger.info("Adjustments applied")

    # Exit
    logger.info("<<<<<<<<<<<<<<<<END>>>>>>>>>>>>>>>>>")

if __name__ == "__main__":
    check_make_adjustments()