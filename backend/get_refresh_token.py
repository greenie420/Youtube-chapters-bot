"""
Run this ONCE on your own computer -- never in GitHub Actions -- to get a
refresh token that lets the bot post chapter comments as you.

Setup:
  1. pip install -r backend/requirements-setup.txt
  2. In Google Cloud Console, create an OAuth Client ID of type
     "Desktop app" and download it as client_secret.json into this
     backend/ folder (see README.md for the full walkthrough).
  3. Run: python backend/get_refresh_token.py
  4. A browser window opens asking you to log in as the YouTube channel
     owner and approve access. Approve it.
  5. Copy the three printed values into your GitHub repo's Actions secrets.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def main():
    flow = InstalledAppFlow.from_client_secrets_file("backend/client_secret.json", SCOPES)
    creds = flow.run_local_server(port=8080)
    print("\nSuccess! Add these as GitHub repo secrets (Settings -> Secrets and variables -> Actions):\n")
    print(f"YT_CLIENT_ID={creds.client_id}")
    print(f"YT_CLIENT_SECRET={creds.client_secret}")
    print(f"YT_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
