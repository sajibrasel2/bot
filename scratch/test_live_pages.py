import urllib.request
import ssl
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

urls = [
    "https://techandclick.site/bot/",
    "https://techandclick.site/bot/videos.html",
    "https://techandclick.site/bot/girls.html",
    "https://techandclick.site/bot/voice.html",
    "https://techandclick.site/bot/wheel.html",
    "https://techandclick.site/bot/categories.html"
]

print("=== Checking Live Server URLs on techandclick.site ===")
for url in urls:
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'}
        )
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
            has_tg_overlay = 'id="tg-forceadd-overlay"' in content
            has_age_overlay = 'id="age-gate-overlay"' in content
            has_inline_style = '.tg-forceadd-overlay' in content
            has_v4 = 'app.js?v=4.0' in content or 'style.css?v=4.0' in content
            
            print(f"\n[URL]: {url}")
            print(f"  - Status Code: {resp.status}")
            print(f"  - Has Telegram Force-Add Modal HTML: {has_tg_overlay}")
            print(f"  - Has Inline Mobile Responsive CSS: {has_inline_style}")
            print(f"  - Has Cache-Buster v4.0: {has_v4}")
    except Exception as e:
        print(f"\n[URL]: {url} -> ERROR: {e}")
