import asyncio
import re

URL_PATTERN = re.compile(
    r"(https?://|ftp://|www\.|t\.me/|telegram\.me/|telegram\.dog/|tg://|"
    r"wa\.me/|discord\.gg/|bit\.ly/|tinyurl\.com/|cutt\.ly/|rb\.gy/|is\.gd/|"
    r"\b[a-zA-Z0-9.-]+\.(com|net|org|io|me|info|xyz|site|top|online|club|live|vip|link|app|co|bd|in|gg|ly|be|cc|ru|biz|tech|store|shop|pro|win|fun|icu|page)\b(/[^\s]*)?)",
    re.IGNORECASE
)

def check_has_link(text):
    return bool(text and URL_PATTERN.search(text))

async def simulate_link_check(user_id, first_name, text, user_invites, required_invites=10):
    has_link = check_has_link(text)
    if not has_link:
        return {"action": "ALLOW_NO_LINK"}
    
    if user_invites >= required_invites:
        return {"action": "ALLOW_INVITES_PASSED", "user_invites": user_invites}
    else:
        remaining = required_invites - user_invites
        alert_text = (
            f"🔗 লিংক শেয়ার লক করা আছে!\n"
            f"👤 ইউজার: {first_name}\n"
            f"🆔 ইউজার আইডি: {user_id}\n"
            f"📊 আপনার বর্তমান অগ্রগতি: {user_invites}/{required_invites} জন\n"
            f"👉 আরও {remaining} জন মেম্বার অ্যাড করলে লিংক শেয়ারিং অটোমেটিক আনলক হবে!"
        )
        return {"action": "BLOCK_LINK_AND_ALERT", "alert": alert_text, "remaining": remaining}

async def main():
    print("Testing link detection...")
    assert check_has_link("Hello world") == False
    assert check_has_link("Check this out https://youtube.com/watch?v=123") == True
    assert check_has_link("Join t.me/mygroup") == True
    assert check_has_link("visit mywebsite.xyz now") == True

    print("Testing 3 invites (under 10)...")
    res_under = await simulate_link_check(123456789, "Rahim", "Visit https://google.com", 3, 10)
    assert res_under["action"] == "BLOCK_LINK_AND_ALERT"
    assert "123456789" in res_under["alert"]
    assert "3/10" in res_under["alert"]
    assert res_under["remaining"] == 7
    print("Under 10 test PASSED!")

    print("Testing 10 invites (unlocked)...")
    res_unlocked = await simulate_link_check(123456789, "Rahim", "Visit https://google.com", 10, 10)
    assert res_unlocked["action"] == "ALLOW_INVITES_PASSED"
    print("10 invites test PASSED!")

    print("Testing 15 invites (unlocked)...")
    res_15 = await simulate_link_check(123456789, "Rahim", "Visit https://google.com", 15, 10)
    assert res_15["action"] == "ALLOW_INVITES_PASSED"
    print("15 invites test PASSED!")

    print("ALL UNIT TESTS PASSED SUCCESSFULLY! ✅")

if __name__ == "__main__":
    asyncio.run(main())
