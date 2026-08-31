"""
02. Reading metadata
--------------------
"""

import requests
from HelpFunctions import webxi_helper_functions as webxi_helper

host, ip = webxi_helper.set_host_ip(__file__)


"""
DisplayScheme is a node that determines wether the display is dark or light.
This node is under "/webxi/applications/slm/setup/displayscheme"
"""
response = requests.get(host + "/webxi/applications/slm/setup/displayscheme")
print(response.text)

"""
This will either be 1 or 0 based on the current color.
To learn the meaning of 1 and 0, we need the metadata of the node.
Get this by using "?metadata" in the url. (also "indent" to make it easier to read)
"""
response = requests.get(host + "/webxi/applications/slm/setup/displayscheme?metadata&indent")
print(response.text)

