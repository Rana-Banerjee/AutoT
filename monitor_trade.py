import logging
from logging.handlers import RotatingFileHandler
from api_helper import ShoonyaApiPy
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import pyotp
import pandas as pd
from datetime import datetime, timedelta, date

### Add condition for exception, when index moves way beyond adjustment
import yaml
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

live = config['live']
target_profit = config['target_profit']
stop_loss = config['stop_loss']
enter_today = config['enter_today']
delta_threshold = config['delta_threshold']
nse_sym_path = config['nse_sym_path']
nfo_sym_path = config['nfo_sym_path']
Expiry = config['Expiry']
Symbol = config['Symbol']
nifty_nse_token = config['nifty_nse_token']
min_strike_price = config['min_strike_price']
max_strike_price = config['max_strike_price']
lot_size = config['lot_size']
lots = config['lots']

# Global variables
#  Initialize the API

api = ShoonyaApiPy()

symbolDf= None
edate = Expiry.split("-")
tsym_prefix= Symbol+edate[0]+edate[1]+edate[2][-2:]
email_subject = "Trade Analytics"

# Logging Setup
logger = logging.getLogger('Auto_Trader')
logger.setLevel(logging.DEBUG)  # Set the logging level for the logger
# Rotating file handler (file size limit of 1 MB, keeps 5 backup files)
file_handler = RotatingFileHandler('logs/app.log', maxBytes=1_000_000, backupCount=5)
# Create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

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


# Step 1: Preprocess data and extract necessary information
def get_current_positions():
    global day_m2m
    # Fetch the latest data (positions, LTP, etc.)
    open_pos_data=[]
    ret = api.get_positions()
    if ret is None:
        # Return test positions
        positions_df= pd.read_csv("test_position.csv")
        return positions_df, -10
        # return None, None
    else:
        mtm = 0
        pnl = 0
        for i in ret:
            mtm += float(i['urmtom'])
            pnl += float(i['rpnl'])
            day_m2m = mtm + pnl
            if int(i['netqty'])!=0:
                # {'buy_sell':'B', 'tsym': pe_hedge, 'qty': lots*lot_size, 'remarks':f'Initial PE Hedg with premium: {pe_hedge_premium}'},
                # rev_buy_sell = {"B": "C", "C": "B"}.get(i['buy_sell'])
                if int(i['netqty'])<0:
                    buy_sell = 'S'
                elif int(i['netqty'])>0:
                    buy_sell = 'B'
                open_pos_data.append({'buy_sell': buy_sell, 'tsym':i['tsym'], 'qty': i['netqty'], 'remarks':'Existing Order', 'netavgprc': i['netavgprc'], 'lp':i['lp'], 'ord_type':i['tsym'][12]})
        positions_df = pd.DataFrame(open_pos_data)
    
        return positions_df, day_m2m

def execute_basket(orders_df):
    # {'buy_sell':'B', 'tsym': pe_hedge, 'qty': lots*lot_size, 'remarks':f'Initial PE Hedg with premium: {pe_hedge_premium}'},
    # place_order(buy_sell, tsym, qty, remarks="regular order")
    for i, order in orders_df.iterrows():
        place_order(order['buy_sell'], order['tsym'], order['qty'], order['remarks'])


def exit_positions(orders_df):
    # {'buy_sell':'B', 'tsym': pe_hedge, 'qty': lots*lot_size, 'remarks':f'Initial PE Hedg with premium: {pe_hedge_premium}'},
    # place_order(buy_sell, tsym, qty, remarks="regular order")
    for i, order in orders_df.iterrows():
        rev_buy_sell = {"B": "S", "S": "B"}.get(order['buy_sell'])
        place_order(rev_buy_sell, order['tsym'], abs(int(order['qty'])), order['remarks'])

def get_Option_Chain(type):
    global symbolDf
    if symbolDf is None:
        symbolDf = pd.read_csv(nfo_sym_path)
        symbolDf['hundred_strikes'] = symbolDf['TradingSymbol'].apply(lambda x: x[-2:])
    
    df=symbolDf[
        (symbolDf.OptionType==type) 
        & (symbolDf.Symbol==Symbol)
        & (symbolDf.Expiry==Expiry) 
        & (symbolDf['hundred_strikes']=="00")
        & (symbolDf['StrikePrice']>min_strike_price) & (symbolDf['StrikePrice']<max_strike_price)
        ]
    
    OList=[]
    for i in df.index:
        strikeInfo = df.loc[i]
        res=api.get_quotes(exchange="NFO", token=str(strikeInfo.Token))
        res={'oi':res['oi'], 'tsym':res['tsym'], 'lp':float(res['lp']), 'lotSize':strikeInfo.LotSize, 'token':res['token'], 'StrikePrice':int(float(res['strprc']))}
        OList.append(res)
    Ostrikedf = pd.DataFrame(OList)
    return Ostrikedf

def get_nearest_price_strike(df, ltp):
    df['price_diff']=abs(df['lp']-ltp)
    df.sort_values(by='price_diff', inplace=True)
    return df.iloc[0]['tsym'], df.iloc[0]['lp']

def get_nearest_strike_strike(df, strike):
    df['strike_diff']=abs(df['StrikePrice']-strike)
    df.sort_values(by='strike_diff', inplace=True)
    return df.iloc[0]['tsym'], df.iloc[0]['lp']

def get_support_resistence_atm(cedf,pedf):
    cedf.sort_values(by='oi', ascending = False, inplace=True)
    pedf.sort_values(by='oi', ascending = False, inplace=True)
    support = int(pedf.iloc[0]['tsym'][13:])
    support_oi = pedf.iloc[0]['oi']
    resistance = int(cedf.iloc[0]['tsym'][13:])
    resistance_oi = cedf.iloc[0]['oi']
    if (support+resistance)/2 % 100 == 0.0:
        atm = (support+resistance)/2
    elif support_oi>resistance_oi:
        atm = (support+resistance-100)/2
    else:
        atm = (support+resistance+100)/2
    return atm

def calculate_initial_positions(base_strike_price, CEOptdf, PEOptdf):
    ce_sell, ce_premium = get_nearest_strike_strike(CEOptdf, base_strike_price)
    pe_sell, pe_premium = get_nearest_strike_strike(PEOptdf, base_strike_price)
    tot_premium=pe_premium+ce_premium
    pe_breakeven = base_strike_price - tot_premium
    ce_breakeven = base_strike_price + tot_premium
    ce_hedge, ce_hedge_premium = get_nearest_strike_strike(CEOptdf, ce_breakeven)
    pe_hedge, pe_hedge_premium = get_nearest_strike_strike(PEOptdf,pe_breakeven)
    orders_df = pd.DataFrame([ 
        {'buy_sell':'B', 'tsym': pe_hedge, 'qty': lots*lot_size, 'remarks':f'Initial PE Hedg with premium: {pe_hedge_premium}'},
        {'buy_sell':'S', 'tsym': pe_sell,  'qty': lots*lot_size, 'remarks':f'Initial PE Sell with premium: {pe_premium}'},
        {'buy_sell':'S', 'tsym': ce_sell,  'qty': lots*lot_size, 'remarks':f'Initial CE Sell with premium: {ce_premium}'},
        {'buy_sell':'B', 'tsym': ce_hedge, 'qty': lots*lot_size, 'remarks':f'Initial CE Hedg with premium: {ce_hedge_premium}'},
    ])
    logger.info(orders_df)
    logger.info(f"Cash required: {pe_hedge_premium+ ce_hedge_premium}")
    print(orders_df)
    print(f"Cash required: {pe_hedge_premium+ ce_hedge_premium}")
    return orders_df
    

def enter_trade():
    # global CEstrikedf, PEstrikedf
    print("Getting CE Option Chain...")
    CEOptdf=get_Option_Chain("CE")
    print("Getting PE Option Chain...")
    PEOptdf=get_Option_Chain("PE")

    # Get initial trade basis future price

    print("Getting Future Price")
    future_price_df = symbolDf[(symbolDf.Symbol=="NIFTY")&(symbolDf.Expiry==Expiry) &(symbolDf['OptionType']=="XX")]
    res=api.get_quotes(exchange="NFO", token=str(future_price_df.iloc[0].Token))
    future_strike = float(res['lp'])
    print("Positions based on Future Price")
    logger.info("Positions based on Future Price")
    Fut_ord_df = calculate_initial_positions(future_strike, CEOptdf, PEOptdf)

    # Get initial trade basis current price
    print("Getting Current Price")
    nse_df = pd.read_csv(nse_sym_path)
    nifty_nse_token = nse_df[(nse_df.Symbol=="Nifty 50")&(nse_df.Instrument=="INDEX")].iloc[0]['Token']
    res=api.get_quotes(exchange="NSE", token=str(nifty_nse_token))
    current_strike = float(res['lp'])
    print("Positions based on Current Price")
    logger.info("Positions based on Current Price")
    Curr_ord_df = calculate_initial_positions(current_strike, CEOptdf, PEOptdf)

    # Get initial trade basis oi
    print("Getting positions based on oi support/resistance")
    atm = get_support_resistence_atm(CEOptdf,PEOptdf)
    logger.info("Positions based on Support/Resistance")
    Oi_ord_df = calculate_initial_positions(atm, CEOptdf, PEOptdf)

    # Get initial trade basis combination
    print("Getting combined position")
    comb_atm = round((2*current_strike+future_strike+atm)/400,0)*100
    logger.info("Combined Positions")
    Comb_ord_df = calculate_initial_positions(comb_atm, CEOptdf, PEOptdf)

    # TODO: Get margin requirement for the trades
    # Execute trade:
    execute_basket(Comb_ord_df)
    email_subject = '<<<<<<<< ENTRY MADE >>>>>>>>>>>>'
    logger.info(email_subject)

    return

def place_order(buy_sell, tsym, qty, remarks="regular order"):
    prd_type = 'M'
    exchange = 'NFO' 
    disclosed_qty= lot_size
    price_type = 'MKT'
    price=0
    trigger_price = None
    retention='DAY'
    if live:
        ret = api.place_order(buy_sell, prd_type, exchange, tsym, qty, disclosed_qty, price_type, price, trigger_price, retention, remarks)
        if ret['stat']=="Ok":
            logger.info(f"Order successsful, Order No: {ret['norenordno']}") # Add reject reason
        else:
            logger.info(f"Order failed, Error: {ret['emsg']}")
    else:
        logger.info(f"TEST ORDER PLACEMENT : {buy_sell}, {tsym}, {qty}, {remarks}")
        print((f"TEST ORDER PLACEMENT : {buy_sell}, {tsym}, {qty}, {remarks}"))

def calculate_delta(df):
    # Verify that there are only 2 records
    put_order = df[(df.buy_sell=="S")&(df.ord_type=="P")]
    call_order = df[(df.buy_sell=="S")&(df.ord_type=="C")] 

    pltp= float(put_order.iloc[0]['lp'])
    cltp= float(call_order.iloc[0]['lp'])
    delta = round(100*abs(pltp-cltp)/(pltp+cltp),2)

    pdiff = float(put_order.iloc[0]['netavgprc'])-pltp
    cdiff = float(call_order.iloc[0]['netavgprc'])-cltp
    profit_leg = "C" if  cdiff > pdiff else "P"
    loss_leg = "P" if  cdiff > pdiff else "C"

    pstrike = int(put_order.iloc[0]['tsym'][13:])
    cstrike = int(call_order.iloc[0]['tsym'][13:])

    strategy = 'IF' if pstrike==cstrike else 'IC'

    put_hedge = df[(df.buy_sell=="B")&(df.ord_type=="P")]
    call_hedge = df[(df.buy_sell=="B")&(df.ord_type=="C")] 

    p_hedge_strike = int(put_hedge.iloc[0]['tsym'][13:])
    c_hedge_strike = int(call_hedge.iloc[0]['tsym'][13:])
    pe_hedge_diff= pstrike-p_hedge_strike
    ce_hedge_diff= c_hedge_strike-cstrike

    return delta, pltp, cltp, profit_leg, loss_leg, strategy, pe_hedge_diff, ce_hedge_diff

# Main monitoring and trading function
def monitor_and_execute_trades(target_profit, stop_loss, lots):
    # Login to Shoonya app
    print('Logging in ...')
    login()

    # Get Positions
    positions_df, m2m = get_current_positions()

    # Step 3: Create positions on Day 1
    if positions_df is None:
        if check_day_after_last_thursday() or enter_today:
            enter_trade()
            api.logout()
            return

    # Exit all Trades if Target achieved or Stop loss hit
    if m2m> target_profit:
        logger.info("Target Profit Acheived. Exit Trade")
        exit_positions(positions_df[['buy_sell','tsym','qty','remarks']])
        email_subject = '<<<<<<<< TARGET PROFIT ACHIEVED. EXIT TRADE >>>>>>>>>>>>'
        return
    elif m2m < stop_loss:
        logger.info("Stop Loss hit. Exit Trade")
        email_subject = '<<<<<<<< STOP LOSS HIT. EXIT TRADE >>>>>>>>>>>>'
        exit_positions(positions_df[['buy_sell','tsym','qty','remarks']])
        return

    # Step 4: Check adjustment signal
    delta, pltp, cltp, profit_leg, loss_leg, strategy, pe_hedge_diff, ce_hedge_diff = calculate_delta(positions_df)

    print(delta, pltp, cltp, profit_leg, loss_leg, strategy, pe_hedge_diff, ce_hedge_diff)

    email_subject = f'DELTA: {delta}% , M2M: {m2m}'
    logger.info(email_subject)

    if delta>delta_threshold:
        email_subject = '<<<<<<<< ADJUSTMENT MADE >>>>>>>>>>>>'
        logger.info(email_subject)
        # If Iron Fly
        if strategy=="IF":
            # Exit the loss making leg
            exit_order_df = positions_df[positions_df.ord_type==loss_leg][['buy_sell','tsym','qty','remarks']]
            # exit_positions(exit_order_df)
            #Find new legs
            if loss_leg=="C":
                search_ltp = pltp
                odf = get_Option_Chain("CE")
                L_tsym, lp = get_nearest_price_strike(odf, search_ltp)
                H_strike = int(L_tsym[13:])+ce_hedge_diff 
            else:
                search_ltp = cltp
                odf = get_Option_Chain("PE")
                L_tsym, lp = get_nearest_price_strike(odf, search_ltp)
                H_strike = int(L_tsym[13:])-pe_hedge_diff

            H_tsym, lp = get_nearest_strike_strike(odf, H_strike)

        elif strategy=="IC":
            #Exit Profit making leg
            exit_order_df = positions_df[positions_df.ord_type==profit_leg][['buy_sell','tsym','qty','remarks']]
            # exit_positions(exit_order_df)
            #Find new legs
            if profit_leg=="C":
                search_ltp = pltp
                odf = get_Option_Chain("CE")
                L_tsym, lp = get_nearest_price_strike(odf, search_ltp)
                # Find loss_leg ATM
                loss_atm = int(positions_df[(positions_df.ord_type==loss_leg) & (positions_df.buy_sell=="S")].iloc[0]['tsym'][13:])
                new_strike_price = int(L_tsym[13:]) if int(L_tsym[13:])> loss_atm else loss_atm
                H_strike = new_strike_price+ce_hedge_diff
            else:
                search_ltp = cltp
                odf = get_Option_Chain("PE")
                L_tsym, lp = get_nearest_price_strike(odf, search_ltp)
                # Find loss_leg ATM
                loss_atm = int(positions_df[(positions_df.ord_type==loss_leg) & (positions_df.buy_sell=="S")].iloc[0]['tsym'][13:])
                new_strike_price = int(L_tsym[13:]) if int(L_tsym[13:])< loss_atm else loss_atm
                H_strike = new_strike_price-pe_hedge_diff

            H_tsym, lp = get_nearest_strike_strike(odf, H_strike)

        #Exit Legs:
        exit_positions(exit_order_df)
        # Place leg and hedge orders
        # Place leg and hedge orders
        place_order("B", H_tsym, lots*lot_size, remarks="Adjustment Hedge order")
        place_order("S", L_tsym, lots*lot_size, remarks="Adjustment Sell order")


# Function to check if today is the first day of the month (example)
def get_last_thursday(year, month):
    # Get the last day of the current month
    next_month = month % 12 + 1
    next_year = year + (month // 12)
    last_day_of_month = date(next_year if next_month == 1 else year, next_month, 1) - timedelta(days=1)
    
    # Find the last Thursday of the month
    while last_day_of_month.weekday() != 3:  # Thursday is weekday 3
        last_day_of_month -= timedelta(days=1)
    
    return last_day_of_month

def check_day_after_last_thursday():
    today = date.today()
    
    # Get the last Thursday of the current month
    last_thursday_current_month = get_last_thursday(today.year, today.month)
    
    # If the last Thursday is in the future, get the last Thursday of the previous month
    if last_thursday_current_month > today:
        last_thursday_current_month = get_last_thursday(today.year, today.month - 1)
    
    # Check if today is one day after the last Thursday
    return today == last_thursday_current_month + timedelta(days=1)

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
        logger.info(f"Login failed: {login_response.get('emsg', 'Unknown error')}")
        print('Logged in failed')


# Call the main function periodically to monitor and execute trades
if __name__=="__main__":
    if not os.path.exists('logs'):
        os.makedirs('logs')
    open('logs/app.log', 'w').close()
    monitor_and_execute_trades(target_profit=target_profit, stop_loss=stop_loss, lots=lots)
    # Send mail with log information
    subject = email_subject
    with open('logs/app.log', 'r') as f:
        body = f.read() 
        # Send the email
        send_custom_email(subject, body)