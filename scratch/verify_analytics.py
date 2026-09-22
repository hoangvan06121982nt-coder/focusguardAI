import urllib.request
import json
import sys

def test_endpoint(url):
    print(f"Testing {url} ...", end=" ")
    try:
        req = urllib.request.Request(url)
        # Add basic cookie mapping or sessions if needed. Since we are testing offline data structure,
        # we will run it against the server. Note that some endpoints require login sessions.
        # We will verify if they respond or redirect appropriately.
        with urllib.request.urlopen(req, timeout=5) as response:
            code = response.getcode()
            content = response.read().decode('utf-8')
            try:
                data = json.loads(content)
                print(f"SUCCESS (JSON) - Status {code}")
                return data
            except json.JSONDecodeError:
                print(f"SUCCESS (HTML/Text) - Status {code}")
                return content
    except Exception as e:
        print(f"FAILED - {e}")
        return None

if __name__ == "__main__":
    base_url = "http://127.0.0.1:5001"
    print("--- FocusGuardAI Analytics API Verification ---")
    
    # We will test public routes and structure
    test_endpoint(f"{base_url}/")
    test_endpoint(f"{base_url}/login")
    
    print("\nVerification script done.")
