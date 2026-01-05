import browser_cookie3
from instaloader import Instaloader, ConnectionException
import os

def load_instagram_session_from_firefox():
    """
    Attempts to load an Instagram session from Firefox cookies.
    """
    L = Instaloader(max_connection_attempts=1)

    try:
        # Load cookies from Firefox for the 'instagram.com' domain
        cj = browser_cookie3.firefox(domain_name='instagram.com')
        L.context._session.cookies.update(cj)

        # Test the login status with the imported cookies
        username = L.test_login()
        if not username:
            raise ConnectionException("Not logged in. Are you logged in successfully in Firefox?")

        print(f"Imported session cookie for {username}.")
        L.context.username = username

        # Save the session to a file for faster loading in future runs
        L.save_session_to_file()
        print(f"Saved session to file for {username}.")

        return L, username

    except ConnectionException as e:
        print(f"Cookie import failed: {e}")
        return None, None
    except Exception as e:
        print(f"An error occurred while trying to import cookies: {e}")
        print("Make sure Firefox is closed when running this script, or that 'browser-cookie3' is working correctly on your OS.")
        return None, None

if __name__ == "__main__":
    loader, user = load_instagram_session_from_firefox()
    if loader and user:
        # Example usage: download your own profile
        print(f"Downloading profile: {user}")
        try:
            profile = loader.Profile.from_username(loader.context, user)
            loader.download_profile(profile, profile_pic_only=True)
            print("Download complete.")
        except Exception as e:
            print(f"Failed to download profile: {e}")
