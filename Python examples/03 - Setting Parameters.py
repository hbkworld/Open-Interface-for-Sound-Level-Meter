"""
03. Setting a setup parameter
-----------------------------
"""

import requests
from slm_api.helpers.webxi_helper_functions import set_host
from slm_api.helpers.https_requests import get, put


"""
set_host creates/reads the `slm_ip` file in the project root. If the IP changes, update or delete `slm_ip` to be prompted again.
"""
host = set_host(__file__)


"""
To set the value of a node, use the HTTP PUT request with a JSON value.
We will be using the DisplayScheme node from the metadata example (remember how Light = 0 and Dark = 1)
These two program lines will read the current value, and write the "inverted" value
"""
color = get(host , "/webxi/applications/slm/setup/DisplayScheme").json()
response = put(host , "/webxi/applications/slm/setup/DisplayScheme", json = (1 if (color == 0) else 0))

