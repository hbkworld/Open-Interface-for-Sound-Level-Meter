"""
This is a multi-line comment. Lines between these two marks will be ignored by Pyhton

01. How to get information from the device
------------------------------------------
"""

"""
The interface to the sound level meter consists of 2 parts. The REST protocol and the streaming protocol.
The REST interface is accessed using normal HTTP requests and JSON, in this example done using the "requests" library.
"""
import requests
from slm_api.helpers.webxi_helper_functions import set_host_ip

""""
set_host_ip creates a .txt file in the project root where the slm_ip address lives. If the file already exists it reads the slm ip from the file.
If the slm ip changes you need to manually update this file or delete to create a new
"""
host, ip = set_host_ip(__file__)


"""
The interface is structured as a tree with "/webxi" as the root.
Get the data structure at the root using an HTTP request.
"""
response = requests.get(host + "/webxi")
print(response.text)

"""
Each node in the substructure is itself a tree if the value is an empty JSON object.
The URL of a node is the name of the node appended to the parent node
"""
response = requests.get(host + "/webxi/device")
print(response.text)

"""
This way it is possible to recursivly access the tree, until you reach a value that is not a tree itself
"""
response = requests.get(host + "/webxi/device/hostname")
print(response.text)

"""
It is possible to get the entire tree in one go by specifying ?recursive in a get.
"""
response = requests.get(host + "/webxi?recursive")
print(response.text)

