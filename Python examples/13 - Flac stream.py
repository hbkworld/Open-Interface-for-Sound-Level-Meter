import asyncio
import requests
import threading
import sys
import HelpFunctions.sequence_handler as seq
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np

# Modules to convert webxi data
import webxi.webxi_stream as webxiStream
# Help functions located in HelpFunction folder
# Read these files to get examples on how to communicate with the SLM
import HelpFunctions.stream_handler as stream           # SLM stream functions
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
import HelpFunctions.flac_stream_2_samples as flac2samples
import threading

# FLAC streaming is only available on 2255
ip = "BK2255-000404"
host = "http://" + ip
sequenceID = 157


class streamHandler:
    def __init__(self, startStream=False):
        self.i = 0
        self.max_input = 15.6263 / np.sqrt(2) 
        self.streamInit()
        if startStream:
            self.startStream()
    
    def decode_flac_stream(self, message, fut):
        start = timer()
        package = webxiStream.WebxiStream.from_bytes(message)
        if package.header.message_type == webxiStream.WebxiStream.Header.EMessageType.e_sequence_data:
            # Get the encoded flac block
            flac = package.content.sequence_blocks[0]          
            # Decode the compressed samples and add it to the data bufffer 
            DataBuffer.append(flac2samples.decode(flac, self.calibrationFactor))
            end = timer()
            total = (end - start)
            if 0.0625 < total:
                print(f"TotalTime: {total}")
        if not self.StreamRun:
            fut.set_result(True)

    def get_calibration_factor(self):
        # Calculate calibration factor from the microphone sensitivity
        response = requests.get(f"{host}/WebXi/Applications/SLM/Outputs/Sensitivity")
        assert (response.status_code == 200)
        mic_sens = float(response.text) # V/Pa
        max_lvl = 20 * np.log10((self.max_input / mic_sens) / 20e-6)  # dB SPL re 20 uPa
        self.calibrationFactor = (20e-6 * 10 ** (max_lvl / 20)) / (2 ** 23 - 1) * np.sqrt(2)

    def streamInit(self):
        # Enable audio recording analysis quality
        response = requests.put(f"{host}/WebXi/Applications/SLM/setup/AudioRecordingAnalysisQuality", json = 1)
        assert(response.status_code == 200)
        self.get_calibration_factor()
        self.ID, self.sequence = seq.get_sequence(host, sequenceID)
        # Get URI for stream
        self.uri = stream.setup_stream(host, ip, self.ID, "Flac stream")

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
        self.msg_func = lambda msg : self.decode_flac_stream(msg, fut) 
        # Initilize and run the websocket to retrive data

        loop.create_task(webSocket.next_async_websocket(self.uri, self.msg_func))
        await fut
        meas.stop_measurement(host)
        streamID = stream.get_stream_ID(host, "flac ")
        # Cleaning up and deleting the stream used
        requests.delete(host + "/WebXi/Streams/" + str(streamID))

    def stopStream(self):
        self.StreamRun = False

class FigHandler:
    def __init__(self):
        self.ChunkToShow = 2**16
        self.fftSize = self.ChunkToShow

        # Used to store "old" spectrums for fft averaging 
        self.old  = 0
        self.oldold = 0

        ## Figures        
        self.fig, (self.ax1, self.ax2) = plt.subplots(2,1)
        axis = np.arange(self.ChunkToShow)
        axis = np.flip(axis * -1/2**16)

        # Subplot1 Time data
        self.line1, = self.ax1.plot(axis, np.arange(self.ChunkToShow))
        self.ax1.set_xlim(left=np.min(axis), right=np.max(axis))
        self.ax1.set_ylim(bottom=-2, top=2)
        self.ax1.grid()
        self.ax1.set_xlabel("Time in seconds")
        self.ax1.set_ylabel("Pressure in Pa")

        # Subplot 2 (FFT) 
        # Calculate the frequency vector 
        freq = np.arange((self.fftSize / 2) + 1) / (float(self.fftSize) / 2**16)
        self.line2, = self.ax2.semilogx(freq, np.arange(len(freq)))
        self.ax2.set_xlim(right=np.max(freq))
        self.ax2.set_ylim(bottom=-20, top=130)
        self.ax2.grid()
        self.ax2.set_xlabel("Frequency in Hz")
        self.ax2.set_ylabel("dB SPL re 20 µPa")
        # Window for the fft
        self.win = np.hamming(self.fftSize)
        self.fig.canvas.mpl_connect('close_event', on_close)
        self.fig.tight_layout()

    def _update(self, i):
        signal = DataBuffer.getPart(self.ChunkToShow)
        self.line1.set_ydata(signal)
        # Update the frequency domain subplot2
        freq, s_dbfs = dBfft(signal, 2**16, self.win, ref = 20e-6) #Reference = 20µPa
        # Average the fft for a smoother plot
        avg = s_dbfs/3 + self.old/3 + self.oldold/3 
        self.line2.set_ydata(avg)
        self.oldold = self.old
        self.old = s_dbfs
        if (i % 5 == 0):
            # Autoscale and print min/max values every 0.5 seconds
            min_Pa = np.round(min(signal),2)
            max_Pa = np.round(max(signal),2)    
            fft_peak = np.round(max(avg),2)
            fft_min = np.round(min(avg),2)
            peak_freq = (freq[np.argmax(avg)])
            if (min_Pa != max_Pa):
                self.ax1.set_ylim(bottom = min_Pa * 1.2, top=max_Pa * 1.2)
            if(np.isinf(fft_peak) == False):
                self.ax2.set_ylim(bottom = fft_min, top=fft_peak * 1.2)
            print(f"Min amplitude: {min_Pa:.2f} Pa, Max amplitude: {max_Pa:.2f} Pa, FFT peak amplitude: {fft_peak:.2f} dB SPL, FFT peak frequency: {peak_freq:.2f} Hz")

    def startAnimation(self):
        self.ani = FuncAnimation(self.fig, self._update, interval=100)

def on_close(event):
    streamer.stopStream()
    sys.exit(0)

if __name__ == "__main__":
    streamer = streamHandler()
    fig = FigHandler()
    threading.Thread(target=streamer.startStream).start()
    threading.Thread(target=fig.startAnimation()).start()
    plt.show()
 