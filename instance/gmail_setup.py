"""One-time Gmail OAuth2 credential setup for larrylilia's account.

Prerequisites:
  1. Go to Google Cloud Console → APIs & Services → Credentials
  2. Create an OAuth 2.0 Client ID (Desktop app type)
  3. Download the JSON and save it as instance/gmail_client_secret.json
  4. Enable the Gmail API for your project

Then run:
    python instance/gmail_setup.py

This opens a browser for larrylilia to authorize access.
The resulting token is saved to instance/gmail_token.json.
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

INSTANCE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET = os.path.join(INSTANCE_DIR, 'gmail_client_secret.json')
TOKEN_FILE = os.path.join(INSTANCE_DIR, 'gmail_token.json')


def main():
    if not os.path.exists(CLIENT_SECRET):
        print(f'ERROR: {CLIENT_SECRET} not found.')
        print('Download your OAuth2 client secret from Google Cloud Console.')
        return
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_FILE, 'w') as f:
        f.write(creds.to_json())
    print(f'Token saved to {TOKEN_FILE}')
    print('Restart the Flask server and visit /gmail/inbox.')


if __name__ == '__main__':
    main()
