import sys
import os
sys.path.insert(0, os.path.abspath("."))
from modules.welcome import _build_button

settings = {}

print("Generating Welcome Button Set 1:")
kb1 = _build_button(settings)
for row in kb1.inline_keyboard:
    print(f"  [{row[0].text.encode('ascii', 'backslashreplace').decode()}] -> {row[0].url}")

print("\nGenerating Welcome Button Set 2:")
kb2 = _build_button(settings)
for row in kb2.inline_keyboard:
    print(f"  [{row[0].text.encode('ascii', 'backslashreplace').decode()}] -> {row[0].url}")

print("\nGenerating Welcome Button Set 3:")
kb3 = _build_button(settings)
for row in kb3.inline_keyboard:
    print(f"  [{row[0].text.encode('ascii', 'backslashreplace').decode()}] -> {row[0].url}")

print("\nAll sets generated successfully!")
