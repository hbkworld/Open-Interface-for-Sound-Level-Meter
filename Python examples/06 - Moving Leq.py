import socket
from slm_api.helpers import webxi_helper_functions as webxi_helper 
from slm_api.helpers.stream_handlers import WebXiStreamHandler



host, ip = webxi_helper.set_host_ip(__file__)
socket.gethostbyname(socket.gethostname())

# Setup streaming info 
"""Sequence 6 is logging LAeq, but this is not guaranteed. """
sequenceId = 6


if __name__ == "__main__":
    streamer = WebXiStreamHandler(host, ip, sequenceID=sequenceId)
    streamer.startStream()
