import threading

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np

from slm_api.helpers.stream_handlers import WebXiStreamHandler
from slm_api.helpers.webxi_helper_functions import set_host_ip
from slm_api.enums.sequence_id_enum import SequenceIdEnums
from slm_api.helpers.data_handler import DataHandler
from slm_api.helpers import webxi_helper_functions as webxi_helper 


"""
set_host_ip creates/reads the `slm_ip` file in the project root. If the IP changes, update or delete `slm_ip` to be prompted again.
"""
host, ip = set_host_ip(__file__)

# Setup what sequence to stream on
sequenceID = SequenceIdEnums.LAeq.value
sequenceName = SequenceIdEnums.LAeq.name


class PrintHandler(DataHandler):
    """Handler to control what gets printed. It must subclass DataHandler and
        implement a handle() method. If unsure what data is available, print data
        itself to see it in the terminal, e.g.:
            def handle(self, **data):
                print(data)
    """
    def handle(self, value, **data):
        print(f"{sequenceName}: " + "%.1f" % value)

class FigHandler:  
   
    def __init__(self, dataHandler):
        self.fig, self.ax = plt.subplots(1,1)
        self.dataHandler = dataHandler if isinstance(dataHandler, list) else [dataHandler]
        axis = np.arange(-(len(self.dataHandler[0].getPlotData(True)) - 1),1,1)
        self.ln = []
        for x in self.dataHandler:
            self.ln.append((self.ax.plot(axis,x.getPlotData(False), label=sequenceName))[0])
        self.ax.set_xlim(left=np.min(axis), right=np.max(axis))
        self.ax.set_ylim(bottom=30, top=100)
        self.ax.set_xlabel("Time [s]")
        self.ax.set_ylabel("dB [SPL]")
        self.ax.set_title('Instantaneous')
        # leg = self.ax.legend(loc='upper left')
        self.ax.grid()
        self.fig.autofmt_xdate()
        self.fig.tight_layout()
        self.fig.canvas.mpl_connect('close_event', on_close)
        self.fig.canvas.setWindowTitle(f'{sequenceName} example') 

    def _update(self, i): 
        for idx, x in enumerate(self.dataHandler):
            self.ln[idx].set_ydata(x.getPlotData(False))

    def startAnimation(self):
        self.ani = FuncAnimation(self.fig, self._update, interval=1000)                      

def on_close(event):
    streamer.stopStream()

if __name__ == "__main__":
    # turns off all BB freq weights to prevent interference
    webxi_helper.turn_off_bb_freq_weight(host)
    
    # turns on the wanted BB freq weights for this example
    webxi_helper.turn_on_bb_freq_weight(host, ['A'])
    
    # sets the sequences to true.
    webxi_helper.turn_on_bb_leq(host, ['LAeq'])

    # WebXiStreamHandler takes several parameters to control what data is streamed:
    # host, ip     - needed to connect to the device
    # sequenceID   - an enum selecting which sequence to listen on
    # leq_window_sec sets the moving average window length in seconds, default is 10 if not specified
    streamer = WebXiStreamHandler(host, ip, sequenceID=sequenceID)
    # To print incoming data, call setDataHandler() with an instance of your own
    # DataHandler subclass (see the PrintHandler class above for an example).
    streamer.setDataHandler(PrintHandler())
    # Plot the streamer's own moving Leq, since it's the one being updated by incoming stream data
    fig = FigHandler(streamer.leq_mov)
    fig.startAnimation()
    # Starts the stream in another thread to not conflict with the figurehandler
    threading.Thread(target=streamer.startStream, daemon=True).start()        
    plt.show()
    
