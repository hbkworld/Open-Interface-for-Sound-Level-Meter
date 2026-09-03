import threading

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np

from slm_api.helpers.stream_handlers import WebXiStreamHandler
from slm_api.helpers.webxi_helper_functions import set_host_ip
from slm_api.enums.sequence_id_enum import SequenceIdEnums


host, ip = set_host_ip(__file__)
sequenceID = SequenceIdEnums.LAeq.value


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
    streamer = WebXiStreamHandler(host, ip, sequenceID=sequenceID, leq_window_sec=10, time=True)
    # Plot the streamer's own moving Leq, since it's the one being updated by incoming stream data
    fig = FigHandler(streamer.leq_mov)
    fig.startAnimation()
    threading.Thread(target=streamer.startStream, daemon=True).start()        
    plt.show()
    