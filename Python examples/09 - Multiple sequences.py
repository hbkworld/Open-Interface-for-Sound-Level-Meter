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
from slm_api.helpers.data_handler import DataHandler
from slm_api.helpers.stream_handler import delete_stream
from slm_api.helpers.measurment_handler import stop_measurement

"""
set_host_ip creates/reads the `slm_ip` file in the project root. If the IP changes, update or delete `slm_ip` to be prompted again.
"""
host, ip = webxi_helper.set_host_ip(__file__)

# This example will stream 2 sequences, LAeq and LCeq. If more sequences is wanted add to this list
# Incase of error make sure the sequences are enabled on the SLM.
sequenceNames = ["LAeq", "LCeq"]


class PrintHandler(DataHandler):
    """Handler to control what gets printed. It must subclass DataHandler and
    implement a handle() method. If unsure what data is available, print data
    itself to see it in the terminal, e.g.:
    def handle(self, **data):
    print(data)
    """
    def handle(self, *, timestamp, name, value, moving_avg):
        print(f"{timestamp}{name}: {value} and 10s test avg: {moving_avg:.2f}")


if __name__ == "__main__":
    # turns off all BB freq weights to prevent interference
    webxi_helper.turn_off_bb_freq_weight(host)

    # turns on the wanted BB freq weights for this example
    webxi_helper.turn_on_bb_freq_weight(host, ["A", "C"])

    # sets the sequences to true. You can add or remove sequences at the top of the file.
    webxi_helper.turn_on_bb_leq(host, sequenceNames)

    streamer = None
    try:
        # WebXiStreamHandler takes several parameters to control what data is streamed:
        # host, ip - needed to connect to the device
        # multi = True because we're streaming more than one sequence at once
        # sequenceNames - names of the already-enabled sequences to look up and stream
        # leq_window_sec - moving average window length in seconds for each sequence
        #   (default 10 if not specified); alternatively use windowSize to set the raw sample count
        streamer = WebXiStreamHandler(host, ip, sequenceNames=sequenceNames, multi=True)
        # To print incoming data, call setDataHandler() with an instance of your own
        # DataHandler subclass (see the PrintHandler class above for an example).
        streamer.setDataHandler(PrintHandler())
        streamer.startStream()
    except KeyboardInterrupt:
        # stops the recording
        stop_measurement(host)
        if streamer is not None:
            # deletes the stream from the device
            delete_stream(host, streamer.streamName)
        print("\nStream stopped by user.") 

 
