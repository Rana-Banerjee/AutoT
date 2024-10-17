from api_helper import ShoonyaApiPy
api = ShoonyaApiPy()
# Login to the API
login_response = api.login(userid=user_id, password=password, twoFA=twoFA, vendor_code='FA417461_U', api_secret='456cdec44eae982782376e77101a6698', imei='abc1234')   
if login_response['stat'] == 'Ok':
    print("Login successful!")
else:
    print(f"Login failed: {login_response['message']}")
    exit