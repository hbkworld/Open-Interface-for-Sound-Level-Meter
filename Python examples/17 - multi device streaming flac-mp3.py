"""
Multi-device FLAC/mp3 audio streaming
--------------------------------------
Streams FLAC- (or mp3-)encoded audio from several devices at once and plots
each device's waveform + spectrum, same as flac_example.py/mp3_example.py's
figureHandler, stacked in one window (one time/freq row pair per device).

Note: WebXiStreamHandler._msg_func_audio also appends decoded samples to the
module-level `DataBuffer` (helpers/buffer.py), which is a single shared buffer.
With multiple devices, samples from all of them interleave in that shared
buffer, so it isn't usable for per-device plotting here - each device instead
gets its own `buffer` instance (BufferDataHandler below).
"""

import sys
import time

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtWidgets

from slm_api.helpers.buffer import buffer as Buffer
from slm_api.helpers.fft import dBfft
from slm_api.helpers.stream_handlers import WebXiStreamHandler, start_all_synced, stop_all
from slm_api.helpers.data_handler import DataHandler
from slm_api.enums.sequence_id_enum import SequenceIdEnums

# Sequence and sample to use for mp3 streaming
# SEQUENCE_ID = SequenceIdEnums.MP3Signal.value 
# SAMPLE_RATE = 32e3
# stream_mode = "mp3"

# Sequence and sample rate to use for Flac streaming
SEQUENCE_ID = SequenceIdEnums.FLACSignal.value
SAMPLE_RATE = 2 ** 16
stream_mode = "flac"

# samples pulled per plot update, i.e. the FFT window size and displayed time-domain length
CHUNK_TO_SHOW = 2 ** 15  

class BufferDataHandler(DataHandler):
    """Per-device handler: appends decoded samples into its own buffer instead
    of the shared DataBuffer singleton, so devices don't mix samples together."""

    def __init__(self):
        self.buffer = Buffer(2 ** 16)

    def handle(self, samples, **data):
        self.buffer.append(samples)


class MultiDeviceFigureHandler:
    """One time-domain + spectrum plot pair per device, stacked in one window."""

    def __init__(self, labels_and_handlers):
        pg.setConfigOptions(antialias=False, useOpenGL=True)
        self.labels_and_handlers = labels_and_handlers
        self.fft_hamming = np.hamming(CHUNK_TO_SHOW)
        self.axis = np.flip(np.arange(CHUNK_TO_SHOW) * -1 / CHUNK_TO_SHOW)
        self.old = [0] * len(labels_and_handlers)
        self.oldold = [0] * len(labels_and_handlers)
        self.i = 0

        self.app = QtWidgets.QApplication(sys.argv)
        self.win = pg.GraphicsLayoutWidget(title="Multi-device streaming")
        self.win.setBackground('w')
        self.win.resize(1000, 300 * len(labels_and_handlers))
        label_style = {'color': '#000', 'font-size': '13pt'}

        self.plots_time, self.plots_freq, self.curves_time, self.curves_freq = [], [], [], []
        freq = np.arange(CHUNK_TO_SHOW // 2 + 1) / (float(CHUNK_TO_SHOW) / SAMPLE_RATE)
        for label, _ in labels_and_handlers:
            plot_time = self.win.addPlot(title=label)
            curve_time = plot_time.plot(self.axis, np.zeros(CHUNK_TO_SHOW))
            curve_time.setPen(color='b', width=2, autoDownsample=True, clipToView=True)
            plot_time.showGrid(x=True, y=True)
            plot_time.setXRange(np.min(self.axis), np.max(self.axis))
            plot_time.setYRange(-2, 2)
            plot_time.getAxis('left').setLabel('Pressure', units='Pa', **label_style)
            plot_time.getAxis('bottom').setLabel('Time', units='s', **label_style)
            self.win.nextRow()

            plot_freq = self.win.addPlot()
            curve_freq = plot_freq.plot(freq, np.zeros(len(freq)))
            curve_freq.setPen(color='b', width=2, autoDownsample=True, clipToView=True)
            plot_freq.setXRange(0, np.max(freq))
            plot_freq.setYRange(-20, 130)
            plot_freq.getAxis('bottom').enableAutoSIPrefix(enable=False)
            plot_freq.setLogMode(x=True, y=False)
            plot_freq.showGrid(x=True, y=True)
            plot_freq.getAxis('left').setLabel('dB SPL re 20 µPa', **label_style)
            plot_freq.getAxis('bottom').setLabel('Frequency', units='Hz', **label_style)
            self.win.nextRow()

            self.plots_time.append(plot_time)
            self.plots_freq.append(plot_freq)
            self.curves_time.append(curve_time)
            self.curves_freq.append(curve_freq)

        self.win.show()
        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(int(0.1 * 1000))

    def update(self):
        # Recomputing dBfft (32768-sample FFT) for every device on every 100ms
        # tick can hold the GIL long enough to stall the decode threads (seen as
        # audio decode's own "TotalTime" warnings), so only do it every 5th tick.
        if self.i % 5 != 0:
            self.i += 1
            return
        for idx, (label, handler) in enumerate(self.labels_and_handlers):
            signal = handler.buffer.getPart(CHUNK_TO_SHOW)
            x = np.linspace(np.min(self.axis), np.max(self.axis), len(signal))
            freq, s_dbfs = dBfft(signal, SAMPLE_RATE, self.fft_hamming, ref=20e-6)  # Reference = 20µPa
            avg = s_dbfs / 3 + self.old[idx] / 3 + self.oldold[idx] / 3
            self.curves_time[idx].setData(x, signal)
            self.curves_freq[idx].setData(freq, avg)
            self.oldold[idx] = self.old[idx]
            self.old[idx] = s_dbfs
            min_Pa = np.round(min(signal), 2)
            max_Pa = np.round(max(signal), 2)
            fft_peak = np.round(max(avg), 2)
            fft_min = np.round(min(avg), 2)
            peak_freq = freq[np.argmax(avg)]
            if min_Pa != max_Pa:
                self.plots_time[idx].setYRange(min_Pa * 1.2, max_Pa * 1.2)
            if not np.isinf(fft_peak):
                self.plots_freq[idx].setYRange(fft_min, fft_peak * 1.2)
            print(f"{label}  Min: {min_Pa} Pa, Max: {max_Pa} Pa, Peak: {fft_peak} dB SPL, Peak freq: {peak_freq} Hz")
        self.i += 1

    def run(self):
        QtWidgets.QApplication.instance().exec_()


if __name__ == "__main__":
    # This example uses multiple slm's so multiple ips is also needed
    # Insert the ips of your devices inside the devices list
    devices = [
        ("192.168.1.183"),
        ("192.168.1.191"),
    ]

    # Sets up the streamhandler to for all the devices.
    # multi_device=True is important for multi device streaming
    streams = [
        WebXiStreamHandler(
            host=dev_host, sequenceID=SEQUENCE_ID,
            streamName=f"Stream_{dev_host}", multi_device=True,
            mode=stream_mode,
        )
        for dev_host in devices
    ]
    handlers = [BufferDataHandler() for _ in streams]
    for s, h in zip(streams, handlers):
        s.setDataHandler(h)

    fig = MultiDeviceFigureHandler([(s.host, h) for s, h in zip(streams, handlers)])
    fig.app.aboutToQuit.connect(lambda: stop_all(streams))


    # sleep(1) is used to make sure every device has finished setting up their streamhandler
    time.sleep(1)
    # Used to start all the streams at the same time
    start_all_synced(streams)
    fig.run()
