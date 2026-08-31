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
from dotenv import load_dotenv
import os

"""
Create a .env file in the same folder as this script and add a line with the IP = "the ip of your SLM".
"""
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

ip = os.getenv("IP")
if not ip:
    raise RuntimeError('Missing IP. Set IP in a .env file (IP=...) or environment variable.')
host = f"http://{ip}"



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

