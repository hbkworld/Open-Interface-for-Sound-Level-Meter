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
host, ip = webxi_helper.set_host_ip(__file__)


SCALE = 0.01  # Raw Int16 value * SCALE = dB

# WebXi header timestamps are 64-bit fixed-point seconds since the Unix epoch
# (Q32.32): upper 32 bits = whole seconds, lower 32 bits = fraction of a second.
WEBXI_TICKS_PER_SECOND = 2 ** 32


FAST_LOGGING_INTERVAL_MS = FastLogInterval.interval_500ms.value
SEQUENCE_ID = SequenceIdEnums.FastLAF.value


class PrintHandler(DataHandler):
    def handle(self, timestamp, name, local, value, unit):
        print(f"{timestamp}{name} ({local}):  {value:7.2f} {unit}")



if __name__ == "__main__":
    try:
        streamer = WebXiStreamHandler(host, ip, sequenceID = SEQUENCE_ID, fast_logging=True, fast_logging_interval=FAST_LOGGING_INTERVAL_MS)
        streamer.setDataHandler(PrintHandler())

        streamer.startStream()

        # asyncio.run(main())
    except KeyboardInterrupt:
        stop_measurement(host)
        delete_stream(host, streamer.streamName)
        print("\nStream stopped by user.") 
