import socket
from slm_api.helpers import webxi_helper_functions as webxi_helper 
from slm_api.helpers.stream_handlers import WebXiStreamHandler
from slm_api.enums.sequence_id_enum import SequenceIdEnums
from slm_api.helpers.stream_handler import delete_stream
from slm_api.helpers.measurment_handler import stop_measurement
from slm_api.helpers.data_handler import DataHandler



host, ip = webxi_helper.set_host_ip(__file__)
socket.gethostbyname(socket.gethostname())

# Setup streaming info 
sequenceId = SequenceIdEnums.LAeq.value

class PrintHandler(DataHandler):
    def handle(self, timestamp, value, moving_avg):
        print(timestamp + "LAeq: " + "%.1f" % value + "  |  LAeq,mov: " + "%.1f" % moving_avg)


if __name__ == "__main__":

    try:
        streamer = WebXiStreamHandler(host, ip, sequenceID=sequenceId)
        streamer.setDataHandler(PrintHandler())
        streamer.startStream()
    except KeyboardInterrupt:
        stop_measurement(host)
        delete_stream(host, streamer.streamName)
        print("User exited the program")
