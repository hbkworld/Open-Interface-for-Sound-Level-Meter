import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from slm_api.helpers.stream_handlers import WebXiStreamHandler
from slm_api.helpers import webxi_helper_functions as webxi_helper 
from slm_api.enums.sequence_id_enum import SequenceIdEnums
from slm_api.helpers.data_handler import DataHandler


"""
set_host_ip creates/reads the `slm_ip` file in the project root. If the IP changes, update or delete `slm_ip` to be prompted again.
"""
host, ip = webxi_helper.set_host_ip(__file__)

# Weight name used to enable the CPB measurement on the device (builds endpoint CPB{weight})
sequence_names = ["LAeq"]
# Full sequence name used to look up the CPB sequence via WebXiStreamHandler
# (only sequenceNames[0] is used for cpb=True)
cpb_sequence_names = ["CPBLAeq"]

# Setup what sequence to stream on
sequenceID= SequenceIdEnums.CPBLAeq.value   

class PrintHandler(DataHandler):
    """Handler to control what gets printed. It must subclass DataHandler and
    implement a handle() method. If unsure what data is available, print data
    itself to see it in the terminal, e.g.:
        def handle(self, **data):
            print(data)
    """
    def handle(self, values, **data):
        print(f"{values}")



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
    streamer.stopStream()

if __name__ == "__main__":
    # turns off all CPB freq weights
    webxi_helper.turn_off_CPB_freq_weight(host)

    # turns on the CPB freq weight we want to use, in this case A weight
    webxi_helper.turn_on_CPB_freq_weight(host, ["A"])

    # turns on the CPB eq we want to use
    webxi_helper.turn_on_cpb_leq(host, sequence_names)

    # WebXiStreamHandler takes several parameters to control what data is streamed:
    # host, ip - needed to connect to the device
    # sequenceID - an enum selecting which sequence to listen on
    # cpb=True is used to listen on cpb
    # Full sequence name used to look up the CPB sequence via WebXiStreamHandler
    streamer = WebXiStreamHandler(host, ip, sequenceID=sequenceID, cpb=True, sequenceNames=cpb_sequence_names)
    # To print incoming data, call setDataHandler() with an instance of your own
    # DataHandler subclass (see the PrintHandler class above for an example).    
    streamer.setDataHandler(PrintHandler())

    fig = FigureHandler(streamer)
    threading.Thread(target=streamer.startStream, daemon=True).start()
    fig.startAnimation()
    plt.show()
