# This example will show how to stream multiple sequences at the same time using the same stream
# For this example enable the wanted sequences on the device
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from slm_api.helpers.stream_handlers import WebXiStreamHandler
from slm_api.helpers import webxi_helper_functions as webxi_helper 
from slm_api.helpers.data_handler import DataHandler

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
    # handles what functions to call when closing the figure
    streamer.stopStream()
    # writes the data to the saved format
    streamer.data_handler.close()

if __name__ == "__main__":
    # turns off all BB freq weights to prevent interference
    webxi_helper.turn_off_bb_freq_weight(host)

    # turns on the wanted BB freq weights for this example
    webxi_helper.turn_on_bb_freq_weight(host, ["A", "C"])

    # sets the sequences to true. You can add or remove sequences at the top of the file.
    webxi_helper.turn_on_bb_leq(host, sequenceNames)

    # WebXiStreamHandler takes several parameters to control what data is streamed:
    # host, ip     - needed to connect to the device
    # multi = True because we're streaming more than one sequence at once
    # sequenceNames - names of the already-enabled sequences to look up and stream
    # leq_window_sec - moving average window length in seconds for each sequence
    #   (default 10 if not specified); alternatively use windowSize to set the raw sample count
    # saving - "csv", "json", or "pickle"; the format to save data as
    # saving_path  - the file path to save the data to. Remember to call streamer.data_handler.close() to save the data on closure. 
    streamer = WebXiStreamHandler(host, ip, sequenceNames=sequenceNames, multi=True, saving="json", saving_path="file path to save the data")
    # To print incoming data, call setDataHandler() with an instance of your own
    # DataHandler subclass (see the PrintHandler class above for an example). 
    streamer.setDataHandler(PrintHandler())
    fig = FigHandler(streamer.sequenceFuncs)
    fig.startAnimation()
    threading.Thread(target=streamer.startStream, daemon=True).start()        
    plt.show()
