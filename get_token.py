from fyers_apiv3 import fyersModel

CLIENT_ID     = "GOLI3H04KX-100"
SECRET_KEY    = "8WM3BG2QZX"
REDIRECT_URI  = "https://trade.fyers.in/api-login/redirect-uri/index.html"

session = fyersModel.SessionModel(
    client_id=CLIENT_ID,
    secret_key=SECRET_KEY,
    redirect_uri=REDIRECT_URI,
    response_type="code",
    grant_type="authorization_code",
)

# STEP 1: Print the login URL
print("STEP 1: Open this URL in your browser and log in:")
print(session.generate_authcode())
print()

# STEP 2: Paste the auth_code from the redirected URL
auth_code = input("STEP 2: Paste the auth_code here and press Enter: ").strip()
session.set_token(auth_code)

# STEP 3: Exchange for access_token
print("\nGenerating access token...")
response = session.generate_token()

if response.get("access_token"):
    token = response["access_token"]
    print("\nSUCCESS! Here's your access token:\n")
    print(token)

    with open("access_token.txt", "w") as f:
        f.write(token)
    print("\nSaved to access_token.txt")
else:
    print("\nError:", response)