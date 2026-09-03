import socket
from slm_api.helpers import webxi_helper_functions as webxi_helper 
from slm_api.helpers.stream_handlers import WebXiStreamHandler
from slm_api.enums.sequence_id_enum import SequenceIdEnums



host, ip = webxi_helper.set_host_ip(__file__)
socket.gethostbyname(socket.gethostname())

# Setup streaming info 
sequenceId = SequenceIdEnums.LAeq.value


if __name__ == "__main__":
    streamer = WebXiStreamHandler(host, ip, sequenceID=sequenceId)
    streamer.startStream()
