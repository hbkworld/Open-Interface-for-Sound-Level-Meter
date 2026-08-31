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
from HelpFunctions import webxi_helper_functions as webxi_helper


# Modules to convert webxi data
import webxi.webxi_header as webxiHead
import webxi.webxi_stream as webxiStream

import HelpFunctions.sequence_handler as seq            # Get sequences, e.g. LAeq functions
import HelpFunctions.stream_handler as stream           # SLM stream functions
import HelpFunctions.measurment_handler as meas         # Start/pause/Stop measurments functions
from HelpFunctions.Leq import MovingLeq, SLM_Setup_LAeq # Class to hold moving Leq 
import HelpFunctions.websocket_handler as webSocket     # Async functions to control communication

host, ip = webxi_helper.set_host_ip(__file__)

# This example will stream 2 sequences, LAeq and LCeq. If more sequences is wanted add to this list
sequenceNames = ["LAeq", "LCeq"]


def print_data(message, IDs, sequences, sequenceFuncs):
    package = webxiStream.WebxiStream.from_bytes(message)
    if package.header.message_type == webxiStream.WebxiStream.Header.EMessageType.e_sequence_data:
        for ID, sequence, Func in zip(IDs, sequences, sequenceFuncs):
            for data in package.content.sequence_blocks:
                if data.sequence_id == ID:
                    value = stream.data_type_conv(sequence["DataType"], data.values, None)
                    value = (np.array(value) if isinstance(value, list) else value) / 100
                    move = Func.move(value)
                    seqName = sequence["Name"]
                    print(f"{seqName}: {value} and 10s avg: {move:.2f}")

async def main():
    IDs = []
    sequences = []
    sequenceFuncs = []

    for x in sequenceNames:
        ID, sequence = seq.get_sequence(host, seq.getSequenceID(host, x))
        IDs.append(ID)
        sequences.append(sequence)
        sequenceFuncs.append(MovingLeq(10, storedata=True))

    uri = stream.setup_stream(host, ip, IDs, "MultipleSequences")
    # Start a measurement. This is needed to obtain data from the device
    meas.start_pause_measurement(host,True) 

    msg_func = lambda msg : print_data(msg, IDs, sequences, sequenceFuncs)

    await webSocket.next_async_websocket(uri, msg_func)

if __name__ == "__main__":
    # turns off all BB freq weights to prevent interference
    webxi_helper.turn_off_bb_freq_weight(host)

    # turns on the wanted BB freq weights for this example
    webxi_helper.turn_on_bb_freq_weight(host, ["A", "C"])

    # sets the sequences to true. You can add or remove sequences at the top of the file.
    webxi_helper.turn_on_bb_leq(host, sequenceNames)

    asyncio.run(main())
