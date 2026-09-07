import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'c:/xampp/htdocs/bot')

from modules.welcome import VIRAL_BUTTON_SETS, _build_button

print("--- Testing 5 consecutive Welcome Message button generations ---")
for i in range(1, 6):
    markup = _build_button({})
    print(f"\n[Welcome Msg #{i}] Buttons:")
    for row in markup.inline_keyboard:
        for btn in row:
            print(f"  - {btn.text} -> {btn.url}")
