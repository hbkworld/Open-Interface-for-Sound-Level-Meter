# This example will show how to stream multiple sequences at the same time using the same stream
# For this example enable the wanted sequences on the device
import asyncio
import requests
import threading
import sys, traceback
import numpy as np
import time
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation


# Modules to convert webxi data
import webxi.webxi_header as webxiHead
import webxi.webxi_stream as webxiStream

import HelpFunctions.sequence_handler as seq            # Get sequences, e.g. LAeq functions
import HelpFunctions.stream_handler as stream           # SLM stream functions
import HelpFunctions.measurment_handler as meas         # Start/pause/Stop measurments functions
from HelpFunctions.Leq import MovingLeq, SLM_Setup_LAeq # Class to hold moving Leq 
import HelpFunctions.websocket_handler as webSocket     # Async functions to control communication
from slm_api.helpers import webxi_helper_functions as webxi_helper 
from slm_api.helpers.stream_handlers import WebXiStreamHandler

host, ip = webxi_helper.set_host_ip(__file__)

# This example will stream 2 sequences, LAeq and LCeq. If more sequences is wanted add them to this list
sequenceNames = ["LAeq", "LCeq"]

if __name__ == "__main__":
    # turns off all BB freq weights to prevent interference
    webxi_helper.turn_off_bb_freq_weight(host)

    # turns on the wanted BB freq weights for this example
    webxi_helper.turn_on_bb_freq_weight(host, ["A", "C"])

    # sets the sequences to true. You can add or remove sequences at the top of the file.
    webxi_helper.turn_on_bb_leq(host, sequenceNames)

    streamer = WebXiStreamHandler(host, ip, sequenceNames=sequenceNames, multi=True)
    streamer.startStream()
 
