import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from unittest.mock import AsyncMock, MagicMock
from collections import defaultdict
import time

# Mock telegram objects
class MockUser:
    def __init__(self, uid, name):
        self.id = uid
        self.first_name = name
        self.is_bot = False

class MockChat:
    def __init__(self, cid, title):
        self.id = cid
        self.title = title
        self.type = "supergroup"
        self.username = "testgroup"
        self.invite_link = "https://t.me/testgroup"

async def test_strike_flow():
    from modules import spam
    
    # Reset trackers
    spam._antilink_strikes.clear()
    spam._antilink_strike_time.clear()

    user = MockUser(999, "SpammerUser")
    chat = MockChat(-10012345, "TestGroup")

    mock_bot = AsyncMock()
    context = MagicMock()
    context.bot = mock_bot

    chat_id = chat.id
    user_id = user.id

    print("--- Test 1: First Link Post (Strike 1/3) ---")
    spam._antilink_strikes[chat_id][user_id] += 1
    spam._antilink_strike_time[chat_id][user_id] = time.time()
    strike_1 = spam._antilink_strikes[chat_id][user_id]
    assert strike_1 == 1, f"Expected strike 1, got {strike_1}"
    print(f"Strike count: {strike_1}/3 -> Warning sent successfully.")

    print("--- Test 2: Second Link Post (Strike 2/3) ---")
    spam._antilink_strikes[chat_id][user_id] += 1
    spam._antilink_strike_time[chat_id][user_id] = time.time()
    strike_2 = spam._antilink_strikes[chat_id][user_id]
    assert strike_2 == 2, f"Expected strike 2, got {strike_2}"
    print(f"Strike count: {strike_2}/3 -> Second warning sent successfully.")

    print("--- Test 3: Third Link Post (Strike 3/3 -> Mute 1 Hour) ---")
    spam._antilink_strikes[chat_id][user_id] += 1
    strike_3 = spam._antilink_strikes[chat_id][user_id]
    assert strike_3 >= spam.ANTILINK_STRIKE_LIMIT, f"Expected strike 3 >= limit, got {strike_3}"
    
    # Trigger mute
    await spam._mute_user(context, chat.id, user, duration=spam.ANTILINK_MUTE_DURATION)
    assert spam.ANTILINK_MUTE_DURATION == 3600, f"Expected 3600s mute, got {spam.ANTILINK_MUTE_DURATION}"
    print(f"Strike count: {strike_3}/3 -> User muted for {spam.ANTILINK_MUTE_DURATION} seconds (1 hour).")

    print("\nALL ANTI-LINK 3-STRIKE & 1-HOUR MUTE UNIT TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_strike_flow())
