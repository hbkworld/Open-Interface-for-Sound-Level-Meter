"""
05. Read and printout the sound level
-------------------------------------
"""

import requests # Handle reply from server
import pprint as pp # Pretty Print to nicely print out data from the response
import time # For the 'sleep' funtion
from HelpFunctions import webxi_helper_functions as webxi_helper

host, ip = webxi_helper.set_host_ip(__file__)


"""
Run program loop 'forever' to fetch LAF from the SLM (or until aborted, eg by ctrl/c)
Note that the value is stored in the SLM as dB multiplied by 100
"""
while True:
	response = requests.get(host + "/webxi/applications/SLM/Outputs/LAF");
	time.sleep(1)
	pp.pprint(response.json()/100)
