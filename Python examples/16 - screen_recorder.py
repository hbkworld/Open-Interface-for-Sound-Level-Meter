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
from slm_api.helpers.stream_handlers import WebXiStreamHandler

"""
set_host_ip creates/reads the `slm_ip` file in the project root. If the IP changes, update or delete `slm_ip` to be prompted again.
"""
host, ip = set_host_ip(__file__)


class FigHandler:
    def __init__(self, streamer):
        self.streamer = streamer
        self.fig, self.ax = plt.subplots()
        self.ax.axis("off")
        self.im = None
        self.fig.canvas.mpl_connect("close_event", on_close)
        self.fig.canvas.manager.set_window_title("SLM screen (live)")

    def _update(self, i):
        # image_bytes is None until the first PNG block has been received
        data = self.streamer.image_bytes
        if data is None:
            return
        image = np.array(Image.open(io.BytesIO(data)))
        # device screen resolution can change (e.g. rotation), so re-create the image artist if the shape changed
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
    # handles what functions to call when closing the figure
    streamer.stopStream()


if __name__ == "__main__":
    # WebXiStreamHandler takes several parameters to control what data is streamed:
    # host, ip       - needed to connect to the device
    # screen_record  - streams the ScreenImage sequence instead of audio/Leq data
    streamer = WebXiStreamHandler(host, ip, screen_record=True)
    fig = FigHandler(streamer)
    fig.startAnimation()
    # Starts the stream in another thread to not conflict with the figurehandler
    threading.Thread(target=streamer.startStream, daemon=True).start()
    plt.show()
    # removes the stream from the device once the figure is closed
    stream.delete_stream(host, streamer.streamName)