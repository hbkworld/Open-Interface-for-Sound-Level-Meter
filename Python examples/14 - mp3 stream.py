import numpy as np
import pyqtgraph as pg

from timeit import default_timer as timer

# Buffer and decoder for the mp3 stream
from slm_api.helpers.buffer import DataBuffer
from slm_api.helpers.fft import dBfft
import threading

from slm_api.helpers.stream_handlers import WebXiStreamHandler

from HelpFunctions.FigureHandler import FigureHandler
from slm_api.helpers import webxi_helper_functions as webxi_helper 

host, ip = webxi_helper.set_host_ip(__file__)
sequenceID = 156


class figureHandler(FigureHandler):

    def axisConfig(self):
        self.plotTime.getAxis('left').setStyle(tickFont=pg.QtGui.QFont('Arial', 11))
        self.plotTime.getAxis('bottom').setStyle(tickFont=pg.QtGui.QFont('Arial', 11))
        self.plotTime.getAxis('left').setLabel('Approximately pressure', units='Pa', **self.labelStyle)
        self.plotTime.getAxis('bottom').setLabel('Time', units='s', **self.labelStyle)
        self.plotFreq.getAxis('left').setStyle(tickFont=pg.QtGui.QFont('Arial', 14))
        self.plotFreq.getAxis('bottom').setStyle(tickFont=pg.QtGui.QFont('Arial', 14))
        self.plotFreq.getAxis('left').setLabel('Approximately dB SPL re 20 µPa', **self.labelStyle)
        self.plotFreq.getAxis('bottom').setLabel('Frequency', units='Hz', **self.labelStyle)

    def update(self):
        signal = DataBuffer.getPart(self.chunkToShow)
        x = np.linspace(np.min(self.axis), np.max(self.axis), len(signal))
        freq, s_dbfs = dBfft(signal, 32e3, self.fftHamming, ref=20e-6)  #Reference = 20µPa
        # Average the fft for a smoother plot
        avg = s_dbfs / 3 + self.old / 3 + self.oldold / 3
        self.curveTime.setData(x, signal)
        self.curveFreq.setData(freq, avg)
        self.oldold = self.old
        self.old = s_dbfs
        if (self.i % 5 == 0):
            # Autoscale and print min/max values every 0.5 seconds
            min_Pa = np.round(min(signal), 2)
            max_Pa = np.round(max(signal), 2)
            fft_peak = np.round(max(avg), 2)
            fft_min = np.round(min(avg), 2)
            peak_freq = (freq[np.argmax(avg)])
            if (min_Pa != max_Pa):
                self.plotTime.setYRange(min_Pa * 1.2, max_Pa * 1.2)
            if (np.isinf(fft_peak) == False):
                self.plotFreq.setYRange(fft_min, fft_peak * 1.2)
            print(f"Min: {min_Pa} Pa, Max: {max_Pa} Pa, Peak: {fft_peak} dB SPL, Peak freq: {peak_freq} Hz")
        self.i += 1


def on_close():
    streamer.stopStream()


if __name__ == "__main__":
    streamer = WebXiStreamHandler(host, ip, mp3=True, sequenceID=sequenceID)
    fig = figureHandler()
    fig.app.aboutToQuit.connect(on_close)
    threading.Thread(target=streamer.startStream, daemon=True).start()
    fig.run()
