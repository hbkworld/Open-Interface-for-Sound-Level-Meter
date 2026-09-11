from slm_api.helpers import webxi_helper_functions as webxi_helper 
from slm_api.helpers.stream_handlers import WebXiStreamHandler
from slm_api.enums.sequence_id_enum import SequenceIdEnums
from slm_api.helpers.stream_handler import delete_stream
from slm_api.helpers.measurment_handler import stop_measurement
from slm_api.helpers.data_handler import DataHandler
from slm_api.helpers.https_requests import UseHttps
from slm_api.helpers import webxi_helper_functions as webxi_helper 
import datetime



"""
set_host_ip creates/reads the `slm_ip` file in the project root. If the IP changes, update or delete `slm_ip` to be prompted again.
"""
host, ip = webxi_helper.set_host_ip(__file__)

# By default https is enabled
# If https is not needed the line below this shows how to disable it for all request calls
UseHttps(use_https=False)


# Used to create file with a custom name and attach the current date and time to it.
filename = f'name-of-file_{datetime.datetime.now().strftime("%H%M_%m%d%Y")}'


# Setup what sequence to stream on
sequenceId = SequenceIdEnums.LAeq.value
sequenceName = SequenceIdEnums.LAeq.name

class PrintHandler(DataHandler):
    """Handler to control what gets printed. It must subclass DataHandler and
    implement a handle() method. If unsure what data is available, print data
    itself to see it in the terminal, e.g.:
        def handle(self, **data):
            print(data)
    """
    def handle(self, value, **data):
        print(f"{sequenceName}: " + "%.1f" % value)




if __name__ == "__main__":
    # turns off all BB freq weights to prevent interference
    webxi_helper.turn_off_bb_freq_weight(host)

    # turns on the wanted BB freq weights for this example
    webxi_helper.turn_on_bb_freq_weight(host, ['A'])

    # sets the sequences to true.
    webxi_helper.turn_on_bb_leq(host, ['LAeq'])

    streamer = None
    try:
        # WebXiStreamHandler takes several parameters to control what data is streamed:
        #   host, ip        - needed to connect to the device
        #   sequenceID      - an enum selecting which sequence to listen on
        #   leq_window_sec  - moving average window length in seconds (default 10 if not specified)
        #   saving          - "csv", "json", or "pickle"; the format to save data as
        #   saving_path     - the file path to save the data to
        streamer = WebXiStreamHandler(host, ip, sequenceID=sequenceId, saving="csv", saving_path=f"./saved_data/{filename}")
        # To print incoming data, call setDataHandler() with an instance of your own
        # DataHandler subclass (see the PrintHandler class above for an example).
        streamer.setDataHandler(PrintHandler())
        # Start the stream
        streamer.startStream()
    except KeyboardInterrupt:
        # Stop the measurement running on the device
        stop_measurement(host)
        if streamer is not None:
            # Flush/close the CSV file so no buffered rows are lost and saves to file. 
            # Only needed if saving the recording to a file
            streamer.data_handler.close()
            # Remove the stream resource from the device
            delete_stream(host, streamer.streamName)
        print("User exited the program")
