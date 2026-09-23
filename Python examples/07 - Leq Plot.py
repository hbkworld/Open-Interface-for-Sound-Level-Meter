import threading

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np

from slm_api.helpers.stream_handlers import WebXiStreamHandler
from slm_api.helpers.webxi_helper_functions import set_host
from slm_api.enums.sequence_id_enum import SequenceIdEnums
from slm_api.helpers.data_handler import DataHandler, MultiDataHandler
from slm_api.helpers import webxi_helper_functions as webxi_helper 


"""
set_host creates/reads the `slm_ip` file in the project root. If the IP changes, update or delete `slm_ip` to be prompted again.
"""
host = set_host(__file__)

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

class FigHandler(DataHandler):
    def __init__(self, buffer_size=101): # increase buffer_size to increase how many seconds of data the plot shows
        self.buffer = np.full(buffer_size, np.nan)

        self.fig, self.ax = plt.subplots(1, 1)
        axis = np.arange(-(buffer_size - 1), 1)

        self.line = self.ax.plot(axis, self.buffer, label=sequenceName)[0]
        self.ax.set_xlim(axis.min(), axis.max())
        self.ax.set_ylim(0, 100)
        self.ax.set_xlabel("Time [s]")
        self.ax.set_ylabel("dB [SPL]")
        self.ax.set_title("Profile")
        self.ax.grid()
        self.ax.legend()
        self.fig.tight_layout()
        self.fig.canvas.mpl_connect("close_event", on_close)
        self.fig.canvas.setWindowTitle("LAeq example")

    def handle(self, *, value, **data):
        self.buffer = np.append(self.buffer[1:], value)

    def _update(self, _):
        self.line.set_ydata(self.buffer)
        return (self.line,)

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
    # host         - needed to connect to the device
    # sequenceID   - an enum selecting which sequence to listen on
    # leq_window_sec sets the moving average window length in seconds, default is 10 if not specified
    streamer = WebXiStreamHandler(host, sequenceID=sequenceID)
    # To print incoming data, call setDataHandler() with an instance of your own
    # Plot the streamer's own moving Leq, since it's the one being updated by incoming stream data
    fig = FigHandler()
    # Adds FigHandler to datahandler so it also receives the streamed data to create a buffer for the plot
    streamer.setDataHandler(MultiDataHandler(PrintHandler(), fig))
    fig.startAnimation()
    # Starts the stream in another thread to not conflict with the figurehandler
    threading.Thread(target=streamer.startStream, daemon=True).start()        
    plt.show()
    
