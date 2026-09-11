"""
15. Stream FastLAF
-----------------------------------
Streams the FastLAF (LAeq) broadband Leq value from sequence 115
and pretty-prints each received value to the terminal.

Sequence 115 properties:
  Name:            FastLAF
  LocalName:       LAeq
  FunctionType:    BroadbandLeq
  DataType:        Int16
  Scale:           0.01
  Weighting:       A
  AveragingMode:   Linear
  Unit:            dB re 20uPa
"""

from slm_api.helpers import webxi_helper_functions as webxi_helper
from slm_api.helpers.stream_handlers import WebXiStreamHandler
from slm_api.enums.fast_log_intervals_enum import FastLogInterval
from slm_api.enums.sequence_id_enum import SequenceIdEnums
from slm_api.helpers.data_handler import DataHandler
from slm_api.helpers.stream_handler import delete_stream
from slm_api.helpers.measurment_handler import stop_measurement

# ---------- Configuration ---------- 
"""
set_host_ip creates/reads the `slm_ip` file in the project root. If the IP changes, update or delete `slm_ip` to be prompted again.
"""
host, ip = webxi_helper.set_host_ip(__file__)


SCALE = 0.01  # Raw Int16 value * SCALE = dB

# WebXi header timestamps are 64-bit fixed-point seconds since the Unix epoch
# (Q32.32): upper 32 bits = whole seconds, lower 32 bits = fraction of a second.
WEBXI_TICKS_PER_SECOND = 2 ** 32


# FastLogInterval enum index (0-10) to configure on the device; each member maps to a
# fixed interval in ms (e.g. interval_500ms -> 500ms). If omitted, the device's current
# setting is read instead.
FAST_LOGGING_INTERVAL = FastLogInterval.interval_500ms.value
SEQUENCE_ID = SequenceIdEnums.FastLAF.value


class PrintHandler(DataHandler):
    """Handler to control what gets printed. It must subclass DataHandler and
    implement a handle() method. If unsure what data is available, print data
    itself to see it in the terminal, e.g.:
        def handle(self, **data):
            print(data)
    """
    def handle(self, name, local, value, unit, **data):
        print(f"{name} ({local}):  {value:7.2f} {unit}")



if __name__ == "__main__":

    # turns off all BB freq weights to prevent interference
    webxi_helper.turn_off_bb_freq_weight(host)

    # turns on the wanted BB freq weights for this example
    webxi_helper.turn_on_bb_freq_weight(host, ["A"])

    # sets the sequences to true. 
    # For fastlogging add fast=True so it routes to the correct endpoint
    webxi_helper.turn_on_bb_leq(host, 'LAF', fast=True)

    streamer = None
    try:
        # WebXiStreamHandler takes several parameters to control what data is streamed:
        # host, ip - needed to connect to the device
        # sequenceID - an enum selecting which sequence to listen on
        # fast_logging = True to enable fast logging
        # fast_logging_interval - FastLogInterval enum index (0-10), not milliseconds directly;
        #   if omitted, the device's currently configured interval is read instead
        streamer = WebXiStreamHandler(host, ip, sequenceID = SEQUENCE_ID, fast_logging=True, fast_logging_interval=FAST_LOGGING_INTERVAL)
        # To print incoming data, call setDataHandler() with an instance of your own
        # DataHandler subclass (see the PrintHandler class above for an example).
        streamer.setDataHandler(PrintHandler())

        streamer.startStream()

        # asyncio.run(main())
    except KeyboardInterrupt:
        stop_measurement(host)
        if streamer is not None:
            delete_stream(host, streamer.streamName)
        print("\nStream stopped by user.") 
