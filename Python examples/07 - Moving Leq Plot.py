import threading

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np

from slm_api.helpers.stream_handlers import WebXiStreamHandler
from slm_api.helpers.webxi_helper_functions import set_host_ip
from slm_api.enums.sequence_id_enum import SequenceIdEnums
from slm_api.helpers.data_handler import DataHandler

"""
set_host_ip creates/reads the `slm_ip` file in the project root. If the IP changes, update or delete `slm_ip` to be prompted again.
"""
host, ip = set_host_ip(__file__)

# Setup what sequence to stream on
sequenceID = SequenceIdEnums.LAeq.value


class PrintHandler(DataHandler):
    """Handler to control what gets printed. It must subclass DataHandler and
        implement a handle() method. If unsure what data is available, print data
        itself to see it in the terminal, e.g.:
            def handle(self, **data):
                print(data)
    """
    def handle(self, timestamp, value, moving_avg):
        print(timestamp + "LAeq: " + "%.1f" % value + "  |  LAeq,mov: " + "%.1f" % moving_avg)

class FigHandler:  
   
    def __init__(self, dataHandler):
        self.fig = plt.figure()
        self.ax = self.fig.subplots(2,1,sharex=True, sharey=True)
        axis = np.arange(-(len(dataHandler.getPlotData(True)) - 1),1,1)
        self.dataHandler = dataHandler
        self.ln1, = self.ax[0].plot(axis,dataHandler.getPlotData(True))
        self.ln2, = self.ax[1].plot(axis,dataHandler.getPlotData(False))
        self.ax[1].set_xlim(left=np.min(axis), right=np.max(axis))
        self.ax[1].set_ylim(bottom=30, top=100)
        self.ax[0].set_ylabel("dB [SPL]")
        self.ax[1].set_xlabel("Time [s]")
        self.ax[1].set_ylabel("dB [SPL]")
        self.ax[0].set_title('Moving avaraged LAeq')
        self.ax[1].set_title('Instantaneous LAeq')
        self.ax[0].grid()
        self.ax[1].grid()
        self.fig.canvas.mpl_connect('close_event', on_close)
        self.fig.canvas.manager.set_window_title('LAeq example') 

    def _update(self, i): 
        self.ln1.set_ydata(self.dataHandler.getPlotData(True))
        self.ln2.set_ydata(self.dataHandler.getPlotData(False))

    def startAnimation(self):
        self.ani = FuncAnimation(self.fig, self._update, interval=1000)                     

def on_close(event):
    streamer.stopStream()

if __name__ == "__main__":
    # WebXiStreamHandler takes several parameters to control what data is streamed:
    # host, ip     - needed to connect to the device
    # sequenceID   - an enum selecting which sequence to listen on
    # leq_window_sec sets the moving average window length in seconds, default is 10 if not specified
    streamer = WebXiStreamHandler(host, ip, sequenceID=sequenceID, leq_window_sec=10)
    # To print incoming data, call setDataHandler() with an instance of your own
    # DataHandler subclass (see the PrintHandler class above for an example).
    streamer.setDataHandler(PrintHandler())
    # Plot the streamer's own moving Leq, since it's the one being updated by incoming stream data
    fig = FigHandler(streamer.leq_mov)
    fig.startAnimation()
    # Starts the stream in another thread to not conflict with the figurehandler
    threading.Thread(target=streamer.startStream, daemon=True).start()        
    plt.show()
    
