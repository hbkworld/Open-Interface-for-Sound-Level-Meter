"""
04. Setup parameters
--------------------
"""

import requests
from HelpFunctions import webxi_helper_functions as webxi_helper

host, ip = webxi_helper.set_host_ip(__file__)


"""
The "SLM" node under /webxi/applications contains everything related to Sound Level Meter functionallity.
"""
response = requests.get(host + "/webxi/applications/slm")
print(response.text)

"""
Below we will use description from the metadata to find out what each of them does
"""
response = requests.get(host + "/webxi/applications/slm")
nodes = response.json()
for subnode in nodes:
    metadata = requests.get(host + "/webxi/applications/slm/" + subnode + "?metadata")
    print("/" + subnode)
    description = metadata.json()["Metadata"].get("Description", "") #We use .get instead because description might not exist
    print("  Description: " + description)

"""
You can change the value of each of these nodes to change the behavior of the SLM
"""

