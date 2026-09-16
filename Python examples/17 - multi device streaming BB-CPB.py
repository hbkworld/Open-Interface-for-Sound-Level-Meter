"""
17 - multi device streaming with CPB or BB
This example shows how to set up multiple devices to stream a CPB or BB frequency at the same time

"""


import datetime
import time
from slm_api.helpers.stream_handlers import WebXiStreamHandler, start_all_synced, stop_all
from slm_api.helpers.data_handler import DataHandler
from slm_api.enums.sequence_id_enum import SequenceIdEnums
from slm_api.enums.fast_log_intervals_enum import FastLogInterval
from slm_api.helpers import webxi_helper_functions as webxi_helper

# Sets the sequence to stream on, this can be BB or CPB
SEQUENCE_ID = SequenceIdEnums.CPBLAeq.value
SEQUENCE_NAME = SequenceIdEnums.CPBLAeq.name

# If using fast logging this can be used to change the interval
FAST_LOGGING_INTERVAL_MS = FastLogInterval.interval_1000ms.value





class PrintDataHandler(DataHandler):
    def __init__(self, label):
        self.label = label

    def handle(self, value, **data):
        print(f"{self.label}  {SEQUENCE_NAME}: {value}")


if __name__ == "__main__":
    # This example uses multiple slm's so multiple ips is also needed
    # Insert the ips of your devices inside the devices list
    devices = [
        ("http://192.168.0.110", "192.168.0.110"),
        ("http://192.168.0.78", "192.168.0.78"),
    ]

    # Enable the frequencies needed for streaming 
    for dev_host, dev_ip in devices:
        webxi_helper.turn_off_CPB_freq_weight(dev_host)
        webxi_helper.turn_on_CPB_freq_weight(dev_host, "A")
        webxi_helper.turn_on_cpb_leq(dev_host, SEQUENCE_NAME)
        # webxi_helper.turn_off_bb_freq_weight(dev_host)
        # webxi_helper.turn_on_bb_freq_weight(dev_host, "A")
        # webxi_helper.turn_on_bb_leq(dev_host, SEQUENCE_NAME)

    # Sets up the streamhandler to for all the devices.
    # multi_device=True is important for multi device streaming
    streams = []
    for dev_host, dev_ip in devices:
        # if the data is to be saved uncomment the line under this. This will save the data from each device in its own file
        # filename = f'{dev_ip}_{datetime.datetime.now().strftime("%H%M_%m%d%Y")}'
        streams.append(
            WebXiStreamHandler(
                host=dev_host, ip=dev_ip, sequenceID=SEQUENCE_ID,
                streamName=f"Stream_{dev_ip}", multi_device=True, cpb=True,
                # example how to save the data, saving support, "csv","json", "pickle". Important to call the close function, look at the end of the file
                # saving="json", saving_path=f"./saved_data/{filename}"
            )
        )
    # Sets a printhandler for all the streams if printing the data is needed
    for s in streams:
        s.setDataHandler(PrintDataHandler(s.ip))

    # sleep(1) is used to make sure every device has finished setting up their streamhandler
    time.sleep(1)
    # Used to start all the streams at the same time
    start_all_synced(streams)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Stops all the streams at the same time 
        stop_all(streams)

        # Important: close every data handler to flush each device's file.
         # for s in streams:
         #     s.data_handler.close()

        print("\nStreams stopped by user.")