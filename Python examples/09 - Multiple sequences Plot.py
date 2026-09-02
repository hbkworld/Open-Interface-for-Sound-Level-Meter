# This example will show how to stream multiple sequences at the same time using the same stream
# For this example enable the wanted sequences on the device
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from slm_api.helpers.stream_handlers import WebXiStreamHandler
from slm_api.helpers import webxi_helper_functions as webxi_helper 

host, ip = webxi_helper.set_host_ip(__file__)

# This example will stream 2 sequences, LAeq and LCeq. If more sequences is wanted add to this list
# Incase of error make sure the sequences are enabled on the SLM.
sequenceNames = ["LAeq", "LCeq"]


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
    webxi_helper.turn_on_bb_leq(host, sequenceNames)

    streamer = WebXiStreamHandler(host, ip, sequenceNames=sequenceNames, multi=True)
    fig = FigHandler(streamer.sequenceFuncs)
    fig.startAnimation()
    threading.Thread(target=streamer.startStream, daemon=True).start()        
    plt.show()
