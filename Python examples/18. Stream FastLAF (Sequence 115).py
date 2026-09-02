"""
18. Stream FastLAF (Sequence 115)
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

import asyncio
import time
import requests
from datetime import datetime

# Modules to convert webxi data
import webxi.webxi_stream as webxiStream

# Reuse existing help functions
import HelpFunctions.stream_handler as stream
import HelpFunctions.measurment_handler as meas
import HelpFunctions.sequence_handler as seq
import HelpFunctions.websocket_handler as webSocket

# ---------- Configuration ---------- 
ip = "192.168.1.183"
host = "http://" + ip
SEQUENCE_ID = 115
SCALE = 0.01  # Raw Int16 value * SCALE = dB

# WebXi header timestamps are 64-bit fixed-point seconds since the Unix epoch
# (Q32.32): upper 32 bits = whole seconds, lower 32 bits = fraction of a second.
WEBXI_TICKS_PER_SECOND = 2 ** 32

# ControlBBFastLoggingInterval enum -> milliseconds between fast-logged samples.
FAST_LOGGING_INTERVAL_MS = {
    0: 1, 1: 2, 2: 4, 3: 8, 4: 16, 5: 32,
    6: 63, 7: 125, 8: 250, 9: 500, 10: 1000,
}


def webxi_time_to_epoch(header_time):
    """Convert a WebXi header time (Q32.32 fixed-point) to Unix epoch seconds."""
    return header_time / WEBXI_TICKS_PER_SECOND


def get_fast_logging_interval_s(host):
    """Read the configured broadband fast-logging interval and return it in seconds."""
    enum = requests.get(host + "/WebXi/Applications/SLM/Setup/ControlBBFastLoggingInterval").json()
    if enum not in FAST_LOGGING_INTERVAL_MS:
        raise ValueError(f"Unexpected ControlBBFastLoggingInterval value: {enum!r}")
    return FAST_LOGGING_INTERVAL_MS[enum] / 1000.0


def get_sequence_info(host, sequence_id):
    """Fetch and validate sequence 115 from the device."""
    seq_id, sequence = seq.get_sequence(host, sequence_id)
    return seq_id, sequence


def print_data(message, seq_id, sequence, interval_s):
    """Decode a websocket message and pretty-print each value with its own timestamp."""
    package = webxiStream.WebxiStream.from_bytes(message)
    if package.header.message_type != webxiStream.WebxiStream.Header.EMessageType.e_sequence_data:
        return

    # The header time is the time of the first sample; fall back to wall clock if
    # it is not in the expected Q32.32 format/epoch.
    start = webxi_time_to_epoch(package.header.time)
    if abs(start - time.time()) > 86400:
        start = time.time()

    # A 1-second package batches many fast-logged samples.
    samples = []
    for block in package.content.sequence_blocks:
        if block.sequence_id != seq_id:
            continue
        # Determine vector length from sequence metadata or byte count
        vector_length = sequence.get("VectorLength", None)
        if vector_length is None and sequence["DataType"] == "Int16":
            vector_length = len(block.values) // 2
        raw = stream.data_type_conv(sequence["DataType"], block.values, vector_length if vector_length and vector_length > 1 else None)
        if isinstance(raw, list):
            samples.extend(v * SCALE for v in raw)
        else:
            samples.append(raw * SCALE)

    if not samples:
        return

    name = sequence.get('Name', 'FastLAeq')
    local = sequence.get('LocalName', 'LAeq')
    unit = sequence.get('Unit', 'dB re 20uPa')
    for n, v in enumerate(samples):
        timestamp = datetime.fromtimestamp(start + n * interval_s).strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}]  {name} ({local}):  {v:7.2f} {unit}")
    print(f"  >> {len(samples)} sample(s) in this rx block")


async def main():
    # Retrieve sequence metadata from device
    seq_id, sequence = get_sequence_info(host, SEQUENCE_ID)

    interval_s = get_fast_logging_interval_s(host)

    print("=" * 60)
    print(f"  Streaming: {sequence.get('Name', 'FastLAeq')}")
    print(f"  Sequence:  {SEQUENCE_ID}")
    print(f"  Weighting: {sequence.get('AcousticalWeighting', 'A')}")
    print(f"  Unit:      {sequence.get('Unit', 'dB re 20uPa')}")
    print(f"  Interval:  {interval_s * 1000:.0f} ms/sample")
    print("=" * 60)

    STREAM_NAME = "FastLAeqStream"

    # Setup websocket stream for sequence 115
    uri = stream.setup_stream(host, ip, [seq_id], STREAM_NAME)

    # Start measurement (no-op if already running)
    meas.start_pause_measurement(host, True)

    # Stream and print values until interrupted (Ctrl+C)
    msg_func = lambda msg: print_data(msg, seq_id, sequence, interval_s)
    try:
        await webSocket.next_async_websocket(uri, msg_func)
    finally:
        # Delete the stream from the device
        stream_id = stream.get_stream_ID(host, STREAM_NAME)
        if stream_id is not None:
            response = requests.delete(f"{host}/WebXi/Streams/{stream_id}")
            print(f"\nStream deleted (status {response.status_code})")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStream stopped by user.") 