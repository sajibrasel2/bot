import sys
import os

# Ensure cPanel Python 3.11 virtualenv site-packages is included
venv_site = "/home/techandc/virtualenv/public_html/bot/3.11/lib/python3.11/site-packages"
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.insert(0, venv_site)

# Add current folder to python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask app object from web/app.py
from web.app import app as application

