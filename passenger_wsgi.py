import sys
import os

# Path to your application directory
app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)

# If using a virtualenv created via cPanel "Setup Python App",
# Passenger activates it automatically. No manual activation needed.

from app import app as application
