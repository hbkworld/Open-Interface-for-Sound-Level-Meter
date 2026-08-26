import asyncio

import miniaudio
import requests
import sys
import numpy as np
import pyqtgraph as pg

# Modules to convert webxi data
import webxi.webxi_stream as webxiStream
import HelpFunctions.stream_handler as stream  # SLM stream functions
# Start/pause/Stop measurments functions
import HelpFunctions.measurment_handler as meas
# Get sequences,
import HelpFunctions.sequence_handler as seq

# Async functions to control communication
import HelpFunctions.websocket_handler as webSocket
from timeit import default_timer as timer

# Buffer and decoder for the mp3 stream
from HelpFunctions.buffer import DataBuffer
from HelpFunctions.fft import dBfft
import threading

from HelpFunctions.FigureHandler import FigureHandler
from HelpFunctions.tmpFileStateMachine import TmpfileStateMachine
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
ip = os.getenv("IP")
if not ip:
    raise RuntimeError('Missing IP. Set IP in a .env file (IP=...) or environment variable.')
host = f"http://{ip}"
sequenceID = 156




class streamHandler:
    def __init__(self, startStream=False):
        self.i = 0
        self.tmpFileSM = TmpfileStateMachine()
        self.max_input = 15.6263 / np.sqrt(2)
        self.streamInit()
        if startStream:
            self.startStream()

    def decode_mp3_stream(self, message):
        start = timer()
        package = webxiStream.WebxiStream.from_bytes(message)
        if package.header.message_type == webxiStream.WebxiStream.Header.EMessageType.e_sequence_data:
            # Get the encoded mp3 block
            mp3 = package.content.sequence_blocks[0]
            data = self.tmpFileSM.runStateMachine(mp3.frame)
            mp3DecodedData = miniaudio.mp3_read_s16(data)

            DataBuffer.append((np.asarray(mp3DecodedData.samples[-mp3DecodedData.num_frames:], dtype=np.int32) << 8) * self.calibrationFactor)

            end = timer()
            total = (end - start)
            if 0.0625 < total:
                print(f"TotalTime: {total}")
        if not self.StreamRun:
            self._resolve()

    def get_calibration_factor(self):
        # Calculate calibration factor from the microphone sensitivity
        response = requests.get(f"{host}/WebXi/Applications/SLM/Outputs/Sensitivity")
        assert (response.status_code == 200)
        mic_sens = float(response.text) # V/Pa
        max_lvl = 20 * np.log10((self.max_input / mic_sens) / 20e-6)  # dB SPL re 20 uPa
        self.calibrationFactor = (20e-6 * 10 ** (max_lvl / 20)) / (2 ** 23 - 1) * np.sqrt(2)

    def streamInit(self):
        response = requests.put(f"{host}/WebXi/Applications/SLM/setup/AudioRecordingListenQuality", json=1)
        assert (response.status_code == 200)
        self.get_calibration_factor()
        self.ID, self.sequence = seq.get_sequence(host, sequenceID)
        # Get URI for stream
        self.streamName = "Mp3 stream"
        self.uri = stream.setup_stream(host, ip, self.ID, self.streamName)

        # Start a measurement. This is needed to obtain data from the device
        meas.start_pause_measurement(host, True)

    def startStream(self):
        self.StreamRun = True
        asyncio.run(self.runStream())

    async def runStream(self):
        self.loop = asyncio.get_running_loop()
        self.fut = self.loop.create_future()
        # Create lambda function to use for the stream message. In this example is a function
        # call used
        self.msg_func = lambda msg: self.decode_mp3_stream(msg)
        # Initialize and run the websocket to retrieve data

        task = self.loop.create_task(webSocket.next_async_websocket(self.uri, self.msg_func))
        await self.fut
        task.cancel()
        meas.stop_measurement(host)

    def stopStream(self):
        self.StreamRun = False
        # Resolve the future directly; waiting for the next message may never happen
        if hasattr(self, "loop"):
            self.loop.call_soon_threadsafe(self._resolve)
        streamID = stream.get_stream_ID(host, self.streamName)
        requests.delete(host + "/WebXi/Streams/" + str(streamID)) # Cleaning up and deleting the stream used

    def _resolve(self):
        if not self.fut.done():
            self.fut.set_result(True)


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
    streamer = streamHandler()
    fig = figureHandler()
    fig.app.aboutToQuit.connect(on_close)
    threading.Thread(target=streamer.startStream, daemon=True).start()
    fig.run()
