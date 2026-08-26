"""
03. Setting a setup parameter
-----------------------------
"""

import requests
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
ip = os.getenv("IP")
if not ip:
    raise RuntimeError('Missing IP. Set IP in a .env file (IP=...) or environment variable.')
host = f"http://{ip}"

"""
To set the value of a node, use the HTTP PUT request with a JSON value.
We will be using the DisplayScheme node from the metadata example (remember how Light = 0 and Dark = 1)
These two program lines will read the current value, and write the "inverted" value
"""
color = requests.get(host + "/webxi/applications/slm/setup/DisplayScheme").json()
response = requests.put(host + "/webxi/applications/slm/setup/DisplayScheme", json = (1 if (color == 0) else 0))

