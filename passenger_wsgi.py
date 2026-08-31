import sys
import os

# Add current folder to python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask app object from web/app.py
from web.app import app as application
