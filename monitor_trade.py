import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
from api_helper import ShoonyaApiPy
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import pyotp
import pandas as pd
from datetime import datetime, date

# Logging Setup
logger = logging.getLogger('Auto_Trader')
logger.setLevel(logging.DEBUG)  # Set the logging level for the logger
# Rotating file handler (file size limit of 1 MB, keeps 5 backup files)
file_handler = RotatingFileHandler('logs/app.log', maxBytes=1_000_000, backupCount=5)
# Create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Global variables
#  Initialize the API
api = ShoonyaApiPy()
symbolDf= None
cedf=None
pedf=None
Expiry = "28-NOV-2024"
Symbol = "NIFTY"
nifty_nse_token = "26000"
CEstrikedf=None
PEstrikedf=None
positions_data=[]
min_strike_price = 23000
max_strike_price = 27000

IC_Delta_Threshold=0.4
IF_Delta_Threshold=0.5
script_name = 'NIFTY28NOV24'
# Example usage:
target_profit = 1000  # Replace with your target profit
stop_loss = -500  # Replace with your stop loss
lots = 1  # Replace with the number of lots you want to trade
lot_size=25

# Assuming you have the Shoonya API client initialized as 'shoonya_client'
# Example:
# shoonya_client = ShoonyaApiClient(api_key, user_id, password)

def calculate_total_profit_loss(positions_data):
    """
    Calculate the total profit/loss for all positions, taking into account whether
    the position is a SELL or a BUY.
    
    :param positions_data: List of dictionaries representing open positions.
                           Each position should include 'entry_price', 'ltp', 
                           'quantity', and 'side' ('SELL' or 'BUY').
    :return: Total profit or loss.
    """
    total_profit_loss = 0
    
    for pos in positions_data:
        entry_price = pos['entry_price']
        ltp = pos['ltp']
        quantity = pos['quantity']
        side = pos['side']  # 'SELL' or 'BUY'
        
        # Calculate profit/loss based on whether the position is a SELL or a BUY
        if side == 'SELL':
            # For SELL positions, profit increases as LTP decreases
            profit_loss = (entry_price - ltp) * quantity
        elif side == 'BUY':
            # For BUY positions, profit increases as LTP increases
            profit_loss = (ltp - entry_price) * quantity
        else:
            raise ValueError(f"Unknown position side: {side}")
        
        total_profit_loss += profit_loss
    
    return total_profit_loss


# Step 1: Preprocess data and extract necessary information
def preprocess_positions():
    # Fetch the latest data (positions, LTP, etc.)
    positions_data = api.get_positions()  # Placeholder API call
    future_price = api.get_index_future_price('INDEX_NAME')  # Replace with actual index
    
    # TO DO
    # Extract entry price and LTP of options in open positions
    # Example:
    # position_data = [{'symbol': 'NIFTY21NOV17500CE', 'entry_price': 100, 'ltp': 120}, ...]
    
    profit_loss = calculate_total_profit_loss(positions_data)
    
    return positions_data, future_price, profit_loss

# Step 2: Check current profit/loss and exit if target or stop loss hit
def check_profit_loss(profit_loss, target_profit, stop_loss):
    if profit_loss >= target_profit or profit_loss <= stop_loss:
        print("Target/Stop Loss reached, exiting all positions.")
        # Exit all legs and close trade
        exit_all_positions()
        return True
    return False

def exit_all_positions():
    # Add logic to exit all positions using Shoonya API
    print("Exiting all positions...")
    # Example API Call:
    # shoonya_client.exit_positions()

def calculate_breakeven_strikes(short_strike, total_premium):
    """
    Calculate the breakeven strike prices for the Iron Fly strategy, rounded to the nearest 100.
    
    :param short_strike: The strike price of the sold options (PE and CE, since they are the same)
    :param total_premium: The total premium collected from selling the PE and CE options
    :return: Tuple (lower_breakeven, upper_breakeven) rounded to the nearest 100s
    """
    # Calculate the breakeven prices
    lower_breakeven = short_strike - total_premium
    upper_breakeven = short_strike + total_premium
    
    # Round the breakeven prices to the nearest 100s
    lower_breakeven_rounded = round(lower_breakeven / 100) * 100
    upper_breakeven_rounded = round(upper_breakeven / 100) * 100
    
    return lower_breakeven_rounded, upper_breakeven_rounded

def get_Option_Chain(df):
    global CEstrikedf
    OList=[]
    for i in df.index:
        strikeInfo = df.loc[i]
        res=api.get_quotes(exchange="NFO", token=str(strikeInfo.Token))
        res={'oi':res['oi'], 'tsym':res['tsym'], 'lp':float(res['lp']), 'lotSize':strikeInfo.LotSize, 'token':res['token'], 'StrikePrice':int(float(res['strprc']))}
        OList.append(res)
    Ostrikedf = pd.DataFrame(OList)
    return Ostrikedf

def get_nearest_price_strike(ltp, df):
    df['price_diff']=abs(df['lp']-ltp)
    df.sort_values(by='diff', inplace=True)
    return df.iloc[0]['tsym'], df.iloc[0]['lp']

def get_nearest_strike_strike(strike, df):
    df['strike_diff']=abs(df['StrikePrice']-strike)
    df.sort_values(by='strike_diff', inplace=True)
    return df.iloc[0]['tsym'], df.iloc[0]['lp']

def get_initial_positions(base_strike_price):
    ce_sell, ce_premium = get_nearest_strike_strike(base_strike_price, CEstrikedf)
    pe_sell, pe_premium = get_nearest_strike_strike(base_strike_price, PEstrikedf)
    tot_premium=pe_premium+ce_premium
    pe_breakeven = base_strike_price - tot_premium
    ce_breakeven = base_strike_price + tot_premium
    ce_hedge, ce_hedge_premium = get_nearest_strike_strike(ce_breakeven, CEstrikedf)
    pe_hedge, pe_hedge_premium = get_nearest_strike_strike(pe_breakeven, PEstrikedf)
    response = {
        'PE_Hedge':['B', 'P','NFO', pe_hedge, lots*lot_size, lots, 'MKT',0,None,'DAY', f'Initial PE Hedge with premium: {pe_hedge_premium}'],
        'PE_Sell':['S', 'P','NFO', pe_sell, lots*lot_size, lots, 'MKT',0,None,'DAY', f'Initial PE Sell with premium: {pe_premium}'],
        'CE_Sell':['S', 'C','NFO', ce_sell, lots*lot_size, lots, 'MKT',0,None,'DAY', f'Initial CE Sell with premium: {ce_premium}'],
        'CE_Hedge':['B', 'C','NFO', ce_hedge, lots*lot_size, lots, 'MKT',0,None,'DAY', f'Initial CE Hedge with premium: {ce_hedge_premium}'],
    }
    print(response)
    for res in response:
        logger.info(f"{res} : {response[res][0]} {response[res][4]} qty {response[res][3]}")
    return response
    
# Step 3: Create initial positions (Day 1)
def create_initial_positions(lots):
    global symbolDf, cedf, pedf, CEstrikedf, PEstrikedf
    if symbolDf is None:
        symbolDf = pd.read_csv("NFO_symbols.txt")
        symbolDf['hundred_strikes'] = symbolDf['TradingSymbol'].apply(lambda x: x[-2:])
        
    cedf=symbolDf[
        (symbolDf.OptionType=="CE") 
        & (symbolDf.Symbol==Symbol)
        & (symbolDf.Expiry==Expiry) 
        & (symbolDf['hundred_strikes']=="00")
        & (symbolDf['StrikePrice']>min_strike_price) & (symbolDf['StrikePrice']<max_strike_price)
        ]

    pedf=symbolDf[
        (symbolDf.OptionType=="PE")
        & (symbolDf.Symbol==Symbol)
        & (symbolDf.Expiry==Expiry) 
        & (symbolDf['hundred_strikes']=="00")
        & (symbolDf['StrikePrice']>min_strike_price) 
        & (symbolDf['StrikePrice']<max_strike_price)
        ]
    
    if CEstrikedf is None:
        print("Getting CE Option Chain...")
        CEstrikedf=get_Option_Chain(cedf)
    
    if PEstrikedf is None:
        print("Getting PE Option Chain...")
        PEstrikedf=get_Option_Chain(pedf)

    # Get initial trade basis future price

    print("Getting Future Price")
    future_price_df = symbolDf[(symbolDf.Symbol=="NIFTY")&(symbolDf.Expiry==Expiry) &(symbolDf['OptionType']=="XX")]
    res=api.get_quotes(exchange="NFO", token=str(future_price_df.iloc[0].Token))
    future_price = float(res['lp'])
    print("Positions based on Future Price")
    logger.info("Positions based on Future Price")
    F_init = get_initial_positions(future_price)

    # Get initial trade basis current price
    print("Getting Current Price")
    logger.info("Getting Current Price")
    # current_price_df = symbolDf[(symbolDf.Symbol=="NIFTY 50")&(symbolDf.Expiry==Expiry) &(symbolDf['OptionType']=="XX")]
    res=api.get_quotes(exchange="NSE", token=nifty_nse_token)
    current_price = float(res['lp'])
    print("Positions based on Current Price")
    logger.info("Positions based on Current Price")
    C_init = get_initial_positions(current_price)

    # TODO: Get margin requirement for the trades
    # req_margin = 1500

    # logger.info(f"Trade details: Req Cash: {tot_buy_premiums}, Req Collateral: {req_margin/2} * 2, + Taxes&Fees")

    api.logout()
    
    return

def sell_option(option_type, strike_price, lots):
    # Sell option logic using Shoonya API
    print(f"Selling {lots} lots of {option_type} at {strike_price}")
    # Example API Call:
    # shoonya_client.sell_option(option_type, strike_price, lots)

def buy_hedge(option_type, strike_price, lots):
    # Buy hedge logic using Shoonya API
    print(f"Buying hedge {lots} lots of {option_type} at {strike_price}")
    # Example API Call:
    # shoonya_client.buy_option(option_type, strike_price, lots)

# Step 4: Check adjustment signal
def check_adjustment_signal(ce_ltp, pe_ltp):
    diff = round((abs(ce_ltp - pe_ltp) / (ce_ltp + pe_ltp)) * 100,2)
    if diff > 40:
        print(f"Adjustment signal detected. CE LTP: {ce_ltp}, PE LTP: {pe_ltp}, Diff: {diff}%")
        return True
    return False

def find_closest_strike(option_chain, target_ltp, option_type):
    """
    Finds the strike price from the option chain where the LTP is closest to the target LTP.
    
    :param option_chain: List of options with 'strike_price' and 'ltp' for each option
    :param target_ltp: The target LTP (ce_ltp or pe_ltp)
    :param option_type: 'CE' or 'PE' to filter option chain
    :return: Closest strike price
    """
    closest_strike = None
    min_diff = float('inf')
    
    # Iterate through the option chain to find the strike price with LTP closest to target_ltp
    for option in option_chain:
        if option['type'] == option_type:  # Filter for CE or PE
            strike_price = option['strike_price']
            ltp = option['ltp']
            diff = abs(ltp - target_ltp)
            
            if diff < min_diff:
                min_diff = diff
                closest_strike = strike_price
    
    return closest_strike

# Step 5-7: Adjust positions based on signals
def adjust_positions_based_on_strikes(positions_data):
    # Extract the PE and CE options from the positions data
    #TODO: Better way to find pe and ce entries
    pe_position = next((pos for pos in positions_data if 'PE' in pos['symbol']), None)
    ce_position = next((pos for pos in positions_data if 'CE' in pos['symbol']), None)
    
    if not pe_position or not ce_position:
        print("Either PE or CE position is missing, cannot adjust.")
        return
    
    #TODO: Better way to extract strike
    pe_strike = int(pe_position['symbol'].split('PE')[0][-5:])
    ce_strike = int(ce_position['symbol'].split('CE')[0][-5:])
    
    # Get the LTPs and entry prices
    pe_ltp = pe_position['lp']
    ce_ltp = ce_position['lp']

    # netavgprc or cforgavgprc
    pe_entry_price = pe_position['entry_price']
    ce_entry_price = ce_position['entry_price']
    
    pe_profit_loss = (pe_ltp - pe_entry_price) * pe_position['quantity']
    ce_profit_loss = (ce_ltp - ce_entry_price) * ce_position['quantity']
    
    if pe_strike == ce_strike:
        print("PE and CE strikes are the same. Adjusting the loss-making option.")
        
        # Determine which option is loss-making
        if pe_profit_loss < ce_profit_loss:
            print(f"Exiting loss-making PE option @ {pe_strike}")
            pe_hedge_diff = pe_position-pe_hedge_position
            exit_position(pe_position)  # Exit PE and corresponding hedge
            #TODO: Exit hedge
            exit_position(pe_hedge_position) 
            new_strike = find_closest_strike(option_chain, ce_ltp, 'PE')
            sell_option('PE', new_strike, lots)
            buy_hedge('PE', new_strike - pe_hedge_diff, lots)
        else:
            print(f"Exiting loss-making CE option @ {ce_strike}")
            ce_hedge_diff = ce_hedge_position-ce_position
            exit_position(ce_position)  # Exit CE and corresponding hedge
            #TODO: Exit hedge
            exit_position(ce_hedge_position) 
            new_strike = find_closest_strike(option_chain, pe_ltp, 'CE')
            sell_option('CE', new_strike, lots)
            buy_hedge('CE', new_strike + ce_hedge_diff, lots)
    
    else:
        print("PE and CE strikes are different. Adjusting the profit-making option.")
        #TODO: If new_strike crosses PE or CE then stop at IF
        # Determine which option is profit-making
        if pe_profit_loss > ce_profit_loss:
            print(f"Exiting profit-making PE option @ {pe_strike}")
            pe_hedge_diff = pe_position-pe_hedge_position
            exit_position(pe_position)  # Exit PE and corresponding hedge
            #TODO: Exit hedge
            exit_position(pe_hedge_position) 
            new_strike = max(find_closest_strike(option_chain, ce_ltp, 'PE'), pe_strike)  # Avoid lower PE strikes when selling CE
            sell_option('PE', new_strike, lots)
            buy_hedge('PE', new_strike - pe_hedge_diff, lots)
        else:
            print(f"Exiting profit-making CE option @ {ce_strike}")
            ce_hedge_diff = ce_hedge_position-ce_position
            exit_position(ce_position)  # Exit CE and corresponding hedge
            #TODO: Exit hedge
            exit_position(ce_hedge_position) 
            new_strike = min(find_closest_strike(option_chain, pe_ltp, 'CE'), ce_strike)  # Avoid higher CE strikes when selling PE
            sell_option('CE', new_strike, lots)
            buy_hedge('CE', new_strike + ce_hedge_diff, lots)

def exit_position(position):
    # Logic to exit a position and its corresponding hedge
    print(f"Exiting position for {position['symbol']}")
    # Example API Call:
    # shoonya_client.exit_position(position['symbol'])

def sell_option(option_type, strike_price, lots):
    print(f"Selling {lots} lots of {option_type} at {strike_price}")
    # Example API Call:
    # shoonya_client.sell_option(option_type, strike_price, lots)

def buy_hedge(option_type, strike_price, lots):
    print(f"Buying hedge {lots} lots of {option_type} at {strike_price}")
    # Example API Call:
    # shoonya_client.buy_option(option_type, strike_price, lots)

# Main monitoring and trading function
def monitor_and_execute_trades(target_profit, stop_loss, lots):
    # Login to Shoonya app
    print('Logging in ...')
    login()

    # Get Positions
    # positions_data, future_price, profit_loss = preprocess_positions()

    # Step 3: Create positions on Day 1
    if len(positions_data) == 0: # and day_is_first_day():
        create_initial_positions(lots)
        api.logout()
        return
    
    # Step 2: Check profit/loss
    # if check_profit_loss(profit_loss, target_profit, stop_loss):
    #     return  # Exit if target/stop loss hit

    # Step 4: Check adjustment signal
    # TODO: find better way to find ce and pe ltps
    ce_ltp = next(pos['ltp'] for pos in positions_data if 'CE' in pos['symbol'])
    pe_ltp = next(pos['ltp'] for pos in positions_data if 'PE' in pos['symbol'])
    if check_adjustment_signal(ce_ltp, pe_ltp):
        # Step 6-7: Adjust positions
        adjust_positions_based_on_strikes(positions_data, ce_ltp, pe_ltp)

# Function to check if today is the first day of the month (example)
def get_last_thursday(year, month):
    # Get the last day of the month
    last_day_of_month = datetime.date(year, month, 1) + datetime.timedelta(days=32)
    last_day_of_month = last_day_of_month.replace(day=1) - datetime.timedelta(days=1)
    
    # Find the last Thursday of the month
    while last_day_of_month.weekday() != 3:  # Thursday is weekday 3
        last_day_of_month -= datetime.timedelta(days=1)
    
    return last_day_of_month

def day_is_first_day():
    today = datetime.date.today()
    last_thursday = get_last_thursday(today.year, today.month)
    
    # Calculate the Friday and Monday after the last Thursday
    friday_after_last_thursday = last_thursday + datetime.timedelta(days=1)
    monday_after_last_thursday = last_thursday + datetime.timedelta(days=4)
    
    # Check if today is either Friday or Monday after the last Thursday
    return today == friday_after_last_thursday or today == monday_after_last_thursday

def login():
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
        print('Logged in sucessfully')
    else:
        logger.info(f"Login failed: {login_response['message']}")
        print('Logged in failed')


# Call the main function periodically to monitor and execute trades
if __name__=="__main__":
    monitor_and_execute_trades(target_profit=target_profit, stop_loss=stop_loss, lots=lots)

