"""
05. Read and printout the sound level
-------------------------------------
"""

import requests # Handle reply from server
import pprint as pp # Pretty Print to nicely print out data from the response
import time # For the 'sleep' funtion
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

ip = os.getenv("IP")
if not ip:

    raise RuntimeError('Missing IP. Set IP in a .env file (IP=...) or environment variable.')

host = f"http://{ip}"


"""
Run program loop 'forever' to fetch LAF from the SLM (or until aborted, eg by ctrl/c)
Note that the value is stored in the SLM as dB multiplied by 100
"""
while True:
	response = requests.get(host + "/webxi/applications/SLM/Outputs/LAF");
	time.sleep(1)
	pp.pprint(response.json()/100)
