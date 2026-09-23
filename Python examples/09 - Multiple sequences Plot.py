# This example will show how to stream multiple sequences at the same time using the same stream
# For this example enable the wanted sequences on the device
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from slm_api.helpers.stream_handlers import WebXiStreamHandler
from slm_api.helpers import webxi_helper_functions as webxi_helper 
from slm_api.helpers.data_handler import DataHandler, MultiDataHandler
import datetime


"""
set_host creates/reads the `slm_ip` file in the project root. If the IP changes, update or delete `slm_ip` to be prompted again.
"""
host = webxi_helper.set_host(__file__)

# Used to create file with a custom name and attach the current date and time to it.
filename = f'name-of-file_{datetime.datetime.now().strftime("%H%M_%m%d%Y")}'


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
    def handle(self, *, name, value, **data):
        print(f"{name}: {value}")


class FigHandler(DataHandler):
    """Plot raw multi-sequence values received from the stream."""

    def __init__(self, sequence_names, buffer_size=101):
        self.buffers = {
            name: np.full(buffer_size, np.nan)
            for name in sequence_names
        }
        self.fig, self.ax = plt.subplots(1,1)
        axis = np.arange(-(buffer_size - 1), 1, 1)
        self.ln = []
        for name in sequence_names:
            self.ln.append((self.ax.plot(axis, self.buffers[name], label=name))[0])
        self.ax.set_xlim(left=np.min(axis), right=np.max(axis))
        self.ax.set_ylim(bottom=00, top=100)
        self.ax.set_xlabel("Time [s]")
        self.ax.set_ylabel("dB [SPL]")
        self.ax.set_title('Profile')
        self.ax.legend()
        self.ax.grid()
        self.fig.autofmt_xdate()
        self.fig.tight_layout()
        self.fig.canvas.mpl_connect('close_event', on_close)
        self.fig.canvas.setWindowTitle('LAeq example') 

    def handle(self, *, name, value, **data):
        self.buffers[name] = np.append(self.buffers[name][1:], value)

    def _update(self, i): 
        for line, name in zip(self.ln, sequenceNames):
            line.set_ydata(self.buffers[name])

    def startAnimation(self):
        self.ani = FuncAnimation(self.fig, self._update, interval=1000)                         

def on_close(event):
    # handles what functions to call when closing the figure
    streamer.stopStream()
    

if __name__ == "__main__":
    # turns off all BB freq weights to prevent interference
    webxi_helper.turn_off_bb_freq_weight(host)

    # turns on the wanted BB freq weights for this example
    webxi_helper.turn_on_bb_freq_weight(host, ["A", "C"])

    # sets the sequences to true. You can add or remove sequences at the top of the file.
    webxi_helper.turn_on_bb_leq(host, sequenceNames)

    # WebXiStreamHandler takes several parameters to control what data is streamed:
    # host           - needed to connect to the device
    # Use mode= to select the stream type. This example uses multi mode.    
    # sequenceNames  - names of the already-enabled sequences to look up and stream
    # leq_window_sec - moving average window length in seconds for each sequence
    #   (default 10 if not specified); alternatively use windowSize to set the raw sample count
    # saving - "csv", "json", or "pickle"; the format to save data as
    # saving_path    - the file path to save the data to. Remember to call streamer.data_handler.close() to save the data on closure. 
    # This example saves to a "saved_data" folder relative to the current working directory,
    # named after the current time and date. The folder is created below since it must
    # to change the filename edit the variable filename at the top of this file
    streamer = WebXiStreamHandler(host, sequenceNames=sequenceNames, mode='multi', saving="json", saving_path=f"./saved_data/{filename}")
    # To print incoming data, call setDataHandler() with an instance of your own
    # DataHandler subclass (see the PrintHandler class above for an example). 
    fig = FigHandler(sequenceNames)
    streamer.setDataHandler(MultiDataHandler(PrintHandler(),fig))
    fig.startAnimation()
    threading.Thread(target=streamer.startStream, daemon=True).start()        
    plt.show()
