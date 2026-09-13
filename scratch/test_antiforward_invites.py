import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from unittest.mock import AsyncMock, MagicMock
import time

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

class MockMessage:
    def __init__(self, mid, user, chat, forward=True):
        self.message_id = mid
        self.from_user = user
        self.chat = chat
        self.text = "Here is a forwarded post"
        self.caption = ""
        self.entities = []
        self.caption_entities = []
        self.forward_origin = MagicMock() if forward else None
        self.forward_date = 12345678 if forward else None
        self.forward_from = None
        self.forward_from_chat = None
        self.forward_sender_name = None
        self.delete = AsyncMock()

async def test_antiforward_flow():
    from modules import spam
    
    # Reset trackers
    spam._antiforward_strikes.clear()
    spam._antiforward_strike_time.clear()

    user = MockUser(777, "ForwardingUser")
    chat = MockChat(-10012345, "TestGroup")

    mock_bot = AsyncMock()
    context = MagicMock()
    context.bot = mock_bot

    chat_id = chat.id
    user_id = user.id

    print("--- Test 1: First Forward Message (Strike 1/3) ---")
    spam._antiforward_strikes[chat_id][user_id] += 1
    spam._antiforward_strike_time[chat_id][user_id] = time.time()
    strike_1 = spam._antiforward_strikes[chat_id][user_id]
    assert strike_1 == 1, f"Expected strike 1, got {strike_1}"
    print(f"Strike count: {strike_1}/3 -> Forward deleted and warning notice generated.")

    print("--- Test 2: Second Forward Message (Strike 2/3) ---")
    spam._antiforward_strikes[chat_id][user_id] += 1
    spam._antiforward_strike_time[chat_id][user_id] = time.time()
    strike_2 = spam._antiforward_strikes[chat_id][user_id]
    assert strike_2 == 2, f"Expected strike 2, got {strike_2}"
    print(f"Strike count: {strike_2}/3 -> Forward deleted and second warning notice generated.")

    print("--- Test 3: Third Forward Message (Strike 3/3 -> Mute 1 Hour) ---")
    spam._antiforward_strikes[chat_id][user_id] += 1
    strike_3 = spam._antiforward_strikes[chat_id][user_id]
    assert strike_3 >= spam.ANTIFORWARD_STRIKE_LIMIT, f"Expected strike 3 >= limit, got {strike_3}"
    
    # Trigger 1-hour mute
    await spam._mute_user(context, chat.id, user, duration=spam.ANTIFORWARD_MUTE_DURATION)
    assert spam.ANTIFORWARD_MUTE_DURATION == 3600, f"Expected 3600s mute, got {spam.ANTIFORWARD_MUTE_DURATION}"
    print(f"Strike count: {strike_3}/3 -> Forward deleted and user muted for {spam.ANTIFORWARD_MUTE_DURATION} seconds (1 hour).")

    print("\nALL ANTI-FORWARD 10-INVITE & 3-STRIKE (1-HOUR MUTE) TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_antiforward_flow())
