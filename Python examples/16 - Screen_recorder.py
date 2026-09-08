"""
Continuously streams the ScreenImage sequence (Name="ScreenImage", DataType="Byte",
DataFormat="PNG") from the device. Unlike most metadata, this isn't a static REST
resource - it's a streamed sequence, like the FLAC/mp3 audio sequences. Each received
block's raw bytes are already a complete PNG file. The plot is refreshed with each
new image received, like a (low frame rate) screen recording of the device.
"""
import io
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from PIL import Image

from slm_api.helpers import sequence_handler as seq
from slm_api.helpers import stream_handler as stream
from slm_api.helpers import measurment_handler as meas
from slm_api.helpers.webxi_helper_functions import set_host_ip
from slm_api.webxi import webxi_stream

host, ip = set_host_ip(__file__)

SEQUENCE_NAME = "ScreenImage"


class ScreenImageStreamHandler(stream.StreamHandler):
    """Continuously streams the device's ScreenImage sequence, keeping the latest PNG."""

    def __init__(self, host, ip, streamName="ScreenImageStream"):
        super().__init__(streamName)
        self.host = host
        self.ip = ip
        self.image_bytes = None
        self.streamInit()

    def streamInit(self):
        self.ID, self.sequence = seq.get_sequence(self.host, seq.getSequenceID(self.host, SEQUENCE_NAME))
        self.uri = stream.setup_stream(self.host, self.ip, self.ID, self.streamName)
        meas.start_pause_measurement(self.host, True)

    def msg_func(self, message):
        package = webxi_stream.WebxiStream.from_bytes(message)
        if package.header.message_type != webxi_stream.WebxiStream.Header.EMessageType.e_sequence_data:
            return
        for block in package.content.sequence_blocks:
            if block.sequence_id == self.ID and block.values:
                # Keep only the most recently received image; older ones are discarded
                self.image_bytes = bytes(block.values)


class FigHandler:
    def __init__(self, streamer):
        self.streamer = streamer
        self.fig, self.ax = plt.subplots()
        self.ax.axis("off")
        self.im = None
        self.fig.canvas.mpl_connect("close_event", on_close)
        self.fig.canvas.manager.set_window_title("SLM screen (live)")

    def _update(self, i):
        data = self.streamer.image_bytes
        if data is None:
            return
        image = np.array(Image.open(io.BytesIO(data)))
        if self.im is None or self.im.get_array().shape != image.shape:
            self.ax.clear()
            self.ax.axis("off")
            self.im = self.ax.imshow(image)
        else:
            self.im.set_data(image)

    def startAnimation(self):
        # interval controls how often the plot polls for a new image, not how
        # often the device actually sends one
        self.ani = FuncAnimation(self.fig, self._update, interval=500)


def on_close(event):
    streamer.stopStream()


if __name__ == "__main__":
    streamer = ScreenImageStreamHandler(host, ip)
    fig = FigHandler(streamer)
    fig.startAnimation()
    threading.Thread(target=streamer.startStream, daemon=True).start()
    plt.show()
    stream.delete_stream(host, streamer.streamName)

