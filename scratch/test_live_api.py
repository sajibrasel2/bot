import urllib.request
import ssl
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

api_url = "https://techandclick.site/bot/api/check_invites.php?user_id=123456789"
print(f"=== Testing Live API Endpoint: {api_url} ===")
try:
    req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        content = resp.read().decode('utf-8', errors='ignore')
        print("Response JSON:")
        print(content)
        data = json.loads(content)
        print(f"API Success: {data.get('success')}")
        print(f"Message: {data.get('message')}")
except Exception as e:
    print(f"API Error: {e}")
