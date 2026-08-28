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
from HelpFunctions import webxi_helper_functions as webxi_helper

host, ip = webxi_helper.set_host_ip(__file__)

# This example will stream 2 sequences, LAeq and LCeq. If more sequences is wanted add to this list
# Incase of error make sure the sequences are enabled on the SLM.
sequenceNames = ["LAeq", "LCeq"]

    
class streamHandler:

    def __init__(self, startStream = False):
        self.streamInit()
        if startStream:
            self.startStream()

    def streamInit(self):
        self.IDs = []
        self.sequences = []
        self.sequenceFuncs = []

        for x in sequenceNames:
            ID, sequence = seq.get_sequence(host, seq.getSequenceID(host, x))
            self.IDs.append(ID)
            self.sequences.append(sequence)
            self.sequenceFuncs.append(MovingLeq(10, storedata=True, windowSize=100))

        self.streamName = "MultipleSequences"
        self.uri = stream.setup_stream(host, ip, self.IDs, self.streamName)
        # Start a measurement. This is needed to obtain data from the device
        meas.start_pause_measurement(host,True) 

    def startStream(self):
        self.StreamRun = True
        asyncio.run(self.runStream())

    async def runStream(self):
        self.loop = asyncio.get_running_loop()
        self.fut = self.loop.create_future()
        # Create lambda function to use for the stream message. In this example is a function
        # call used
        self.msg_func = lambda msg : self.print_data(msg, self.IDs, self.sequences, self.sequenceFuncs, self.fut) 
        # Initilize and run the websocket to retrive data
        task = self.loop.create_task(webSocket.next_async_websocket(self.uri, self.msg_func))
        await self.fut
        task.cancel()
        meas.stop_measurement(host)

    def stopStream(self):
        self.StreamRun = False  
        if hasattr(self, "loop"):
            self.loop.call_soon_threadsafe(self._resolve)
        stream.delete_stream(host, self.streamName) # Cleaning up and deleting the stream used

    def _resolve(self):
        if not self.fut.done():
            self.fut.set_result(True)

    def print_data(self, message, IDs, sequences, sequenceFuncs, fut):
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
        
        if not self.StreamRun:
            self._resolve()

class FigHandler:  
   
    def __init__(self, dataHandler):
        self.fig, self.ax = plt.subplots(2,1,sharex=True, sharey=True)
        axis = np.arange(-(len(dataHandler[0].getPlotData(True)) - 1),1,1)
        self.dataHandler = dataHandler if isinstance(dataHandler, list) else [dataHandler]
        self.ln1 = []
        self.ln2 = []
        for x, ii in zip(self.dataHandler, sequenceNames):
            self.ln1.append((self.ax[0].plot(axis,x.getPlotData(True), label=ii))[0])
            self.ln2.append((self.ax[1].plot(axis,x.getPlotData(False)))[0])
        self.ax[1].set_xlim(left=np.min(axis), right=np.max(axis))
        self.ax[1].set_ylim(bottom=30, top=100)
        self.ax[0].set_ylabel("dB [SPL]")
        self.ax[1].set_xlabel("Time [s]")
        self.ax[1].set_ylabel("dB [SPL]")
        self.ax[0].set_title('Moving avaraged')
        self.ax[1].set_title('Instantaneous')
        leg = self.ax[0].legend(loc='upper left')
        self.ax[0].grid()
        self.ax[1].grid()
        self.fig.autofmt_xdate()
        self.fig.tight_layout()
        self.fig.canvas.mpl_connect('close_event', on_close)
        self.fig.canvas.setWindowTitle('LAeq example') 

    def _update(self, i): 
        for idx, x in enumerate(self.dataHandler):
            self.ln1[idx].set_ydata(x.getPlotData(True))
            self.ln2[idx].set_ydata(x.getPlotData(False))

    def startAnimation(self):
        self.ani = FuncAnimation(self.fig, self._update, interval=1000)                     

def on_close(event):
    streamer.stopStream()

if __name__ == "__main__":
    # turns off all BB freq weights to prevent interference
    webxi_helper.turn_off_bb_freq_weight(host)

    # turns on the wanted BB freq weights for this example
    webxi_helper.turn_on_bb_freq_weight(host, ["A", "C"])

    # sets the sequences to true. You can add or remove sequences at the top of the file.
    webxi_helper.turn_on_bbl_eq(host, sequenceNames)

    streamer = streamHandler()
    fig = FigHandler(streamer.sequenceFuncs)
    fig.startAnimation()
    threading.Thread(target=streamer.startStream, daemon=True).start()        
    plt.show()
