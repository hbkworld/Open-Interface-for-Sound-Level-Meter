import asyncio
import enum

import miniaudio
import requests
import sys
import numpy as np

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

# Buffer and decoder for the flac stream
from HelpFunctions.buffer import DataBuffer
from HelpFunctions.fft import dBfft
import threading
import tempfile

from HelpFunctions.FigureHandler import FigureHandler

ip = "BK2245-000605"
host = "http://" + ip
sequenceID = 156


class TmpfileStateMachine:
    # tmpfiles are used to store the mp3 data which are used for decoding.
    class State(enum.Enum):
        init = 0
        file1 = 1
        preFile2 = 2
        file2 = 3
        preFile1 = 4

    def __init__(self):
        self.tempFile1 = None
        self.tempFile2 = None
        self.state = self.State.init

    def runStateMachine(self, mp3Data):
        readData = None
        match self.state:
            case self.State.init:
                readData = self.on_init(mp3Data)
            case self.State.file1:
                readData = self.on_file1(mp3Data)
            case self.State.preFile2:
                readData = self.on_preFile2(mp3Data)
            case self.State.file2:
                readData = self.on_file2(mp3Data)
            case self.State.preFile1:
                readData = self.on_preFile1(mp3Data)
        return readData

    def on_init(self, mp3Data):
        if not self.tempFile1:
            self.tempFile1 = tempfile.SpooledTemporaryFile(max_size=1 * 1024 * 1024, mode='w+b', suffix=".mp3",
                                                           prefix="tmp1")
        self.tempFile1.write(bytes(mp3Data))
        self.tempFile1.seek(0)
        dataFromFile = self.tempFile1.read()
        if (len(dataFromFile) > 20 * 1024):
            self.state = self.State.preFile2
        return dataFromFile

    def on_file1(self, mp3Data):
        if self.tempFile2:
            self.tempFile2.close()
            self.tempFile2 = None
        self.tempFile1.seek(0)
        dataFromFile = self.tempFile1.read()
        self.tempFile1.write(bytes(mp3Data))
        if (len(dataFromFile) > 20 * 1024):
            self.state = self.State.preFile2
        return dataFromFile

    def on_preFile2(self, mp3Data):
        if not self.tempFile2:
            self.tempFile2 = tempfile.SpooledTemporaryFile(max_size=1 * 1024 * 1024, mode='w+b', suffix=".mp3",
                                                           prefix="tmp2")
        self.tempFile1.seek(0)
        self.tempFile2.seek(0)
        dataFromFile = self.tempFile1.read()
        tmp = self.tempFile2.read()
        self.tempFile1.write(bytes(mp3Data))
        self.tempFile2.write(bytes(mp3Data))
        if (len(dataFromFile) > 30 * 1024):
            self.state = self.State.file2
        return dataFromFile

    def on_file2(self, mp3Data):
        if self.tempFile1:
            self.tempFile1.close()
            self.tempFile1 = None
        self.tempFile2.seek(0)
        dataFromFile = self.tempFile2.read()
        self.tempFile2.write(bytes(mp3Data))
        if (len(dataFromFile) > 20 * 1024):
            self.state = self.State.preFile1
        return dataFromFile

    def on_preFile1(self, mp3Data):
        if not self.tempFile1:
            self.tempFile1 = tempfile.SpooledTemporaryFile(max_size=1 * 1024 * 1024, mode='w+b', suffix=".mp3",
                                                           prefix="tmp1")
        self.tempFile1.seek(0)
        self.tempFile2.seek(0)
        dataFromFile = self.tempFile2.read()
        tmp = self.tempFile1.read()
        self.tempFile1.write(bytes(mp3Data))
        self.tempFile2.write(bytes(mp3Data))
        if (len(dataFromFile) > 30 * 1024):
            self.state = self.State.file1
        return dataFromFile


class streamHandler:
    def __init__(self, startStream=False):
        self.i = 0
        self.tmpFileSM = TmpfileStateMachine()
        self.max_input = 15.6263 / np.sqrt(2)
        self.streamInit()
        if startStream:
            self.startStream()

    def decode_mp3_stream(self, message, fut):
        start = timer()
        package = webxiStream.WebxiStream.from_bytes(message)
        if package.header.message_type == webxiStream.WebxiStream.Header.EMessageType.e_sequence_data:
            # Get the encoded mp3 block
            mp3 = package.content.sequence_blocks[0]
            data = self.tmpFileSM.runStateMachine(mp3.frame)
            mp3DecodedData = miniaudio.mp3_read_s16(data)

            DataBuffer.append(mp3DecodedData.samples[-mp3DecodedData.num_frames:])

            end = timer()
            total = (end - start)
            if 0.0625 < total:
                print(f"TotalTime: {total}")
        if not self.StreamRun:
            fut.set_result(True)

    def get_calibration_factor(self):
        # Calculate calibration factor from the microphone sensitivity
        response = requests.get(f"{host}/WebXi/Applications/SLM/Setup/TransducerSensitivity")
        assert (response.status_code == 200)
        mic_sens = float(response.text) * 1e-3  # mV/Pa
        max_lvl = 20 * np.log10((self.max_input / mic_sens) / 20e-6)  # dB SPL re 20 uPa
        self.calibrationFactor = (20e-6 * 10 ** (max_lvl / 20)) / (2 ** 23 - 1) * np.sqrt(2)

    def streamInit(self):
        response = requests.put(f"{host}/WebXi/Applications/SLM/setup/AudioRecordingListenQuality", json=1)
        assert (response.status_code == 200)
        self.get_calibration_factor()
        self.ID, self.sequence = seq.get_sequence(host, sequenceID)
        # Get URI for stream
        self.uri = stream.setup_stream(host, ip, self.ID, "Mp3 stream")

        # Start a measurement. This is needed to obtain data from the device
        meas.start_pause_measurement(host, True)

    def startStream(self):
        self.StreamRun = True
        asyncio.run(self.runStream())

    async def runStream(self):
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        # Create lambda function to use for the stream message. In this example is a function
        # call used
        self.msg_func = lambda msg: self.decode_mp3_stream(msg, fut)
        # Initialize and run the websocket to retrieve data

        loop.create_task(webSocket.next_async_websocket(self.uri, self.msg_func))
        await fut
        meas.stop_measurement(host)
        streamID = stream.get_stream_ID(host, "mp3 ")
        # Cleaning up and deleting the stream used
        requests.delete(host + "/WebXi/Streams/" + str(streamID))

    def stopStream(self):
        self.StreamRun = False


class figureHandler(FigureHandler):
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


def on_close(event):
    streamer.stopStream()
    sys.exit(0)


if __name__ == "__main__":
    streamer = streamHandler()
    fig = figureHandler()
    threading.Thread(target=streamer.startStream).start()
    threading.Thread(target=fig.run()).start()
