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

    # Save access token
    with open("access_token.txt", "w") as f:
        f.write(token)
    print("\nSaved to access_token.txt")

    # Save the FULL response (includes refresh_token for automation)
    import json, time
    with open("token_response.json", "w") as f:
        json.dump({
            "access_token": token,
            "refresh_token": response.get("refresh_token"),
            "expires_in": response.get("expires_in"),
            "token_type": response.get("token_type"),
            "created_at": int(time.time()),
        }, f, indent=2)
    print("Saved to token_response.json (refresh_token captured: "
          f"{'YES' if response.get('refresh_token') else 'NO'})")
else:
    print("\nError:", response)