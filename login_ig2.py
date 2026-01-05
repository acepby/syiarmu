import instaloader
import browser_cookie3

L = instaloader.Instaloader()

# Load cookies from Firefox
cj = browser_cookie3.firefox(domain_name='instagram.com')
L.context._session.cookies.update(cj)

# Test login and save session file
username = L.test_login()
if not username:
    raise SystemExit("Not logged in. Are you logged in successfully in Firefox?")
print(f"Imported session cookie for {username}.")
L.save_session_to_file(username)

# Now you can use L for other operations
# For example: L.download_profile(username)
