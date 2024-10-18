# Imports
import logging
from logging.handlers import RotatingFileHandler
import os
import json
import requests
from api_helper import ShoonyaApiPy
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import pyotp

# Global variables
lot_size = 2
IC_Delta_Threshold=0.4
IF_Delta_Threshold=0.5
target=100
stop_loss=100
hedge_points=200
script_name = 'NIFTY NOV'

# Helper function
def send_custom_email(subject, body):
    # Email configuration
    sender_email = os.getenv("EMAIL_USER")
    receiver_email = os.getenv("EMAIL_TO")
    password = os.getenv("EMAIL_PASS")

    logger.info(sender_email+"||"+receiver_email+"||"+password)

    # Create email
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject

    # Add body to email
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect to the Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Upgrade the connection to a secure encrypted SSL/TLS connection
        server.login(sender_email, password)  # Login to your email account
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)  # Send the email
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")
    finally:
        server.quit()

# Logging Setup
logger = logging.getLogger('Auto_Trader')
logger.setLevel(logging.DEBUG)  # Set the logging level for the logger
# Rotating file handler (file size limit of 1 MB, keeps 5 backup files)
file_handler = RotatingFileHandler('logs/app.log', maxBytes=1_000_000, backupCount=5)
# Create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

#  Initialize the API
api = ShoonyaApiPy()

def check_make_adjustments():
    # Start Procedure
    logger.info("<<<<<<<<<<<<<<<<START>>>>>>>>>>>>>>>>>")

    # do_put_adjustment = False
    # do_call_adjustment = False
    # do_extra_call_sell = False
    # do extra_put_sell = False
    
    # Login to the API
    # Your TOTP secret token

    TOKEN = os.getenv("TOKEN")
    userid=os.getenv("userid")
    password=os.getenv("password")
    vendor_code=os.getenv("vendor_code")
    api_secret=os.getenv("api_secret")
    imei=os.getenv("imei")

    twoFA = pyotp.TOTP(TOKEN).now()

    login_response = api.login(userid=userid, password=password, twoFA=twoFA, vendor_code=vendor_code, api_secret=api_secret, imei=imei)   
    if login_response['stat'] == 'Ok':
        logger.info("Login successful!")
    else:
        logger.info(f"Login failed: {login_response['message']}")
        exit(0)

    # Fetch current positions
    logger.info("Positions:")
    positions = api.get_positions()

       
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

    api.logout()
    logger.info("Logged out")
    # Exit
    logger.info("<<<<<<<<<<<<<<<<END>>>>>>>>>>>>>>>>>")
    # Send mail with log information
    subject = "Monitor Log"
    with open('logs/app.log', 'r') as f:
        body = f.read() 
        # Send the email
        send_custom_email(subject, body)
   

if __name__ == "__main__":
    check_make_adjustments()