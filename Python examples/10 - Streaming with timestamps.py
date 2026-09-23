# This example shows how to stream an LAeq stream with timestamps.

from slm_api.helpers import webxi_helper_functions as webxi_helper
from slm_api.helpers.data_handler import DataHandler
from slm_api.helpers.stream_handlers import WebXiStreamHandler

"""
set_host creates/reads the `slm_ip` file in the project root. If the IP changes, update or delete `slm_ip` to be prompted again.
"""
host = webxi_helper.set_host(__file__)


class PrintHandler(DataHandler):
    def handle(self, *, timestamp, name, value, **data):
        print(f"{timestamp}{name}: {value:.2f}")

if __name__ == "__main__":
    streamer = None
    try:
        streamer = WebXiStreamHandler(
            host,
            sequenceNames=["LAeq"],
            streamName="TimestampedLAeq",
            mode="multi",
            time=True,
        )
        streamer.setDataHandler(PrintHandler())
        streamer.startStream()
    except KeyboardInterrupt:
        if streamer is not None:
            streamer.stopStream()