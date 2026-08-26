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
import HelpFunctions.websocket_handler as webSocket     # Async functions to control communication
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
ip = os.getenv("IP")
if not ip:
    raise RuntimeError('Missing IP. Set IP in a .env file (IP=...) or environment variable.')
host = f"http://{ip}"
sequenceID = 35

class CPB_SLM:
    def __init__(self, sequence):
        self.sequence = sequence
        self.msg_func =  lambda msg : self.print_Data(msg, sequence["DataType"] , sequence["VectorLength"])
        self.CPB_values = np.zeros(sequence["VectorLength"])

    def print_Data(self, message, data_type, vectLength):
        package = webxiStream.WebxiStream.from_bytes(message)
        
        if package.header.message_type == webxiStream.WebxiStream.Header.EMessageType.e_sequence_data:
            value = package.content.sequence_blocks[0].values
            self.CPB_values = np.array(stream.data_type_conv(data_type, value, vectLength)) / 100
            print(self.CPB_values)
    
    def calcFreqBands(self):
        octaveRange = np.arange(12,44,3) if self.sequence["VectorLength"] == 11 else np.arange(11,44)
        bb = lambda x : np.round(x * 2) / 2 if  x < 70 else bb(x / 10) * 10
        octaves = 10**(0.1*octaveRange)
        return [bb(i) for i in octaves]

def getSequenceID(host, SqeuenceName):
    sequences = requests.get(host + "/webxi/sequences?recursive").json()
    return seq.find_sequence_by_name(SqeuenceName, sequences)

class streamHandler:
    
    def __init__(self, dataClass, streamName, sequenceID):
        self.dataClass = dataClass
        self.streamName = streamName
        self.sequenceID = sequenceID

    def streamInit(self):
        self.uri = stream.setup_stream(host, ip, self.sequenceID, self.streamName)
        meas.start_pause_measurement(host, True)

    def _streamFunc(self, msg):
        self.dataClass.msg_func(msg)
        if not self.RunStream:
            self._resolve()
    
    def startStream(self):
        self.RunStream = True
        asyncio.run(self.runStream())
    
    async def runStream(self):
        self.loop = asyncio.get_running_loop()
        self.fut = self.loop.create_future()
        self.msg_func = lambda msg : self._streamFunc(msg)
        task = self.loop.create_task(webSocket.next_async_websocket(self.uri, self.msg_func))
        await self.fut
        task.cancel()
        meas.stop_measurement(host)
        

    def stopStream(self):
        self.RunStream = False
        # Only signal here, the stream must stay alive until runStream has finished awaiting
        if hasattr(self, "loop"):
            self.loop.call_soon_threadsafe(self._resolve)
        streamID = stream.get_stream_ID(host, self.streamName)
        requests.delete(host + "/WebXi/Streams/" + str(streamID)) # Cleaning up and deleting the stream used

    def _resolve(self):
        if not self.fut.done():
            self.fut.set_result(True)
       

class FigureHandler:
    
    def __init__(self, dataHandler):
        self.dataHandler = dataHandler
        self.fig, self.ax = plt.subplots(1,1, figsize=(10,5))
        self.CPBFreq = dataHandler.calcFreqBands()
        self.freq = [(i.replace("000.0","k")).replace(".0", "") for i in [str(i) for i in self.CPBFreq]]
        self.ln = self.ax.bar(self.freq, np.zeros(len(self.freq)), width=.99)
        self.ax.set_ylim(bottom=-20, top=120)
        self.ax.grid(axis='y')
        self.ax.set_ylabel("dB [SPL]")
        self.ax.set_xlabel("Frequency band [Hz]")
        self.fig.autofmt_xdate()
        self.fig.tight_layout()
        self.fig.canvas.mpl_connect('close_event', on_close)

    def _update(self, i): 
        for rect, h in zip(self.ln.patches, self.dataHandler.CPB_values):
            rect.set_height(h)

    def startAnimation(self):
        self.ani = FuncAnimation(self.fig, self._update, interval=1000) 

def on_close(event):
    stream_handler.stopStream()

if __name__ == "__main__":
    # makes sure no other CPBFreqWeight is occupying spot 1
    requests.put(host + "/WebXi/Applications/SLM/Setup/CPBFreqWeightB", json=False)
    requests.put(host + "/WebXi/Applications/SLM/Setup/CPBFreqWeightC", json=False)
    requests.put(host + "/WebXi/Applications/SLM/Setup/CPBFreqWeightZ", json=False)
    
    requests.put(host + "/WebXi/Applications/SLM/Setup/CPBFreqWeightA", json=True)
    requests.put(host + "/WebXi/Applications/SLM/Setup/CPBLAeq", json=True)
    ID, sequence = seq.get_sequence(host, getSequenceID(host, "CPBLAeq"))

    CPB_LAeq = CPB_SLM(sequence)
    stream_handler = streamHandler(CPB_LAeq, "CPB test", ID)
    stream_handler.streamInit()
    fig = FigureHandler(CPB_LAeq)
    threading.Thread(target=stream_handler.startStream, daemon=True).start()
    fig.startAnimation()
    plt.show()
