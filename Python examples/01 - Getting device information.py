"""
This is a multi-line comment. Lines between these two marks will be ignored by Pyhton

01. How to get information from the device
------------------------------------------
"""

"""
The interface to the sound level meter consists of 2 parts. The REST protocol and the streaming protocol.
The REST interface is accessed using normal HTTP requests and JSON, in this example done using the "requests" library.
"""

from slm_api.helpers.https_requests import get, UseHttps
from slm_api.helpers.webxi_helper_functions import set_host

"""
set_host creates/reads the `slm_ip` file in the project root. If the IP changes, update or delete `slm_ip` to be prompted again.
"""
host = set_host(__file__)

# By default https is enabled.
# To disable https call the UseHttps class and set use_https=False
UseHttps(use_https=False)

"""
host can also be set manually 
host = ip of the slm
"""


"""
The interface is structured as a tree with "/webxi" as the root.
Get the data structure at the root using an HTTP request.
"""

# import the requests methods from the library "slm_api.helpers.https_requests"
# this library supports get, put, post and delete and uses https by default
# these request calls take host, and end point arguments
# these requests use https by default, see above how to disable https
response = get(host, "/webxi")
print(response.text)

"""
Each node in the substructure is itself a tree if the value is an empty JSON object.
The URL of a node is the name of the node appended to the parent node
"""
response = get(host, "/webxi/device")
print(response.text)

"""
This way it is possible to recursivly access the tree, until you reach a value that is not a tree itself
"""
response = get(host , "/webxi/device/hostname")
print(response.text)

"""
It is possible to get the entire tree in one go by specifying ?recursive in a get.
"""
response = get(host , "/webxi?recursive")
print(response.text)

