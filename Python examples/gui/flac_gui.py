from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import panel as pn
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure

from slm_api.enums.sequence_id_enum import SequenceIdEnums
from slm_api.helpers.fft import dBfft
from slm_api.helpers.https_requests import put
from slm_api.helpers.data_handler import DataHandler
from slm_api.helpers.stream_handlers import WebXiStreamHandler
from slm_api.helpers.webxi_helper_functions import set_host

pn.extension()

SAMPLE_RATE = 2**16
SAMPLE_COUNT = 2**16
FFT_SIZE = 2**15
WAVEFORM_POINTS = 2**11
SPECTRUM_BINS = 512
FFT_INTERVAL = 0.15
FREQUENCY_LIMIT = 20_000
TIME_AXIS = np.arange(WAVEFORM_POINTS) * (SAMPLE_COUNT / SAMPLE_RATE) / WAVEFORM_POINTS
WAVEFORM_INDICES = np.linspace(
    0, SAMPLE_COUNT - 1, WAVEFORM_POINTS, dtype=np.intp
)
FFT_WINDOW = np.hamming(FFT_SIZE)

host_ip = set_host()


class SampleRingBuffer:
    def __init__(self, capacity: int) -> None:
        self._data = np.zeros(capacity, dtype=float)
        self._next = 0
        self._size = 0
        self._lock = threading.Lock()

    def append(self, samples: np.ndarray) -> None:
        with self._lock:
            count = min(samples.size, self._data.size)
            if count == 0:
                return
            values = samples[-count:]
            end = self._next + count
            if end <= self._data.size:
                self._data[self._next:end] = values
            else:
                first = self._data.size - self._next
                self._data[self._next:] = values[:first]
                self._data[: end - self._data.size] = values[first:]
            self._next = end % self._data.size
            self._size = min(self._size + count, self._data.size)

    def snapshot(self, count: int) -> np.ndarray:
        with self._lock:
            result = np.zeros(count, dtype=float)
            available = min(count, self._size)
            if available == 0:
                return result
            start = (self._next - available) % self._data.size
            end = start + available
            if end <= self._data.size:
                result[-available:] = self._data[start:end]
            else:
                first = self._data.size - start
                result[-available:-available + first] = self._data[start:]
                result[-available + first:] = self._data[:end - self._data.size]
            return result


class FlacDataHandler(DataHandler):
    """Append decoded FLAC blocks to a bounded buffer."""

    def __init__(self) -> None:
        self.buffer = SampleRingBuffer(SAMPLE_COUNT * 2)
        self.new_data = threading.Event()

    def handle(self, *, samples: object, **_data: object) -> None:
        _ = _data
        block = np.asarray(samples, dtype=float).reshape(-1)
        if block.size == 0:
            return
        self.buffer.append(block)
        self.new_data.set()

    def snapshot(self) -> np.ndarray:
        return self.buffer.snapshot(SAMPLE_COUNT)


class FFTWorker:
    """Calculate spectra off the Panel/Bokeh document thread."""

    def __init__(self, data_handler: FlacDataHandler) -> None:
        self.data_handler = data_handler
        self.stop_event = threading.Event()
        self.result_lock = threading.Lock()
        self.frequency = np.array([0.0])
        self.levels = np.array([0.0])
        self.thread = threading.Thread(target=self._run, name="flac-fft", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.data_handler.new_data.set()
        self.thread.join(timeout=2)

    def snapshot(self) -> tuple[np.ndarray, np.ndarray]:
        with self.result_lock:
            return self.frequency.copy(), self.levels.copy()

    def _run(self) -> None:
        while not self.stop_event.is_set():
            self.data_handler.new_data.wait(FFT_INTERVAL)
            self.data_handler.new_data.clear()
            if self.stop_event.is_set():
                return
            signal = self.data_handler.snapshot()[-FFT_SIZE:]
            frequency, levels = dBfft(
                signal, SAMPLE_RATE, FFT_WINDOW, ref=20e-6
            )
            limit = min(
                len(frequency),
                int(FREQUENCY_LIMIT / (SAMPLE_RATE / FFT_SIZE)) + 1,
            )
            frequency = frequency[:limit]
            levels = levels[:limit]
            bin_count = min(SPECTRUM_BINS, len(frequency))
            edges = np.linspace(0, len(frequency), bin_count + 1, dtype=np.intp)
            aggregated_frequency = np.empty(bin_count)
            aggregated_levels = np.empty(bin_count)
            for index, (start, end) in enumerate(zip(edges[:-1], edges[1:])):
                end = max(end, start + 1)
                aggregated_frequency[index] = frequency[start:end].mean()
                aggregated_levels[index] = levels[start:end].max()
            with self.result_lock:
                self.frequency = aggregated_frequency
                self.levels = aggregated_levels



host = pn.widgets.TextInput(name="SLM host", value=set_host())
start_button = pn.widgets.Button(name="Start FLAC stream", button_type="primary")
stop_button = pn.widgets.Button(name="Stop stream", button_type="light")
start_pause = pn.widgets.Button(name="start or pause measurement", button_type="light")
status = pn.pane.Alert("Stream stopped.", alert_type="light")

time_source = ColumnDataSource(
    data={"time": TIME_AXIS, "amplitude": np.zeros(WAVEFORM_POINTS)}
)
frequency_source = ColumnDataSource(
    data={"frequency": np.array([0.0]), "level": np.array([0.0])}
)

time_plot = figure(
    title="FLAC waveform",
    height=300,
    sizing_mode="stretch_width",
    x_axis_label="Time [s]",
    y_axis_label="Pressure",
    y_range=(-1,1)
)
time_plot.line("time", "amplitude", source=time_source, line_width=1)

frequency_plot = figure(
    title="FLAC spectrum",
    height=300,
    sizing_mode="stretch_width",
    x_axis_label="Frequency [Hz]",
    y_axis_label="dB SPL re 20 µPa",
    x_range=(0, FREQUENCY_LIMIT),
    y_range=(-30, 70)
)
frequency_plot.line("frequency", "level", source=frequency_source, line_width=2)

streamer: WebXiStreamHandler | None = None
data_handler: FlacDataHandler | None = None
fft_worker: FFTWorker | None = None


def set_status(message: str, alert_type: str = "light") -> None:
    status.object = message
    status.alert_type = alert_type


def start_stream(_event: object) -> None:
    global data_handler, fft_worker, streamer

    _ = _event
    if not host.value.strip():
        set_status("Enter the SLM host before starting the stream.", "warning")
        return

    stop_stream(None)
    try:
        put(
            host.value.strip(),
            "/WebXi/Applications/SLM/Setup/AudioRecordingAnalysisQuality",
            json=1,
        )
        data_handler = FlacDataHandler()
        fft_worker = FFTWorker(data_handler)
        fft_worker.start()
        streamer = WebXiStreamHandler(
            host.value.strip(),
            mode="flac",
            sequenceID=SequenceIdEnums.FLACSignal.value,
        )
        streamer.setDataHandler(data_handler)
        threading.Thread(
            target=streamer.startStream,
            name="flac-stream",
            daemon=True,
        ).start()
        set_status("Streaming FLAC audio.", "success")
    except (AssertionError, OSError, RuntimeError, ValueError) as error:
        if fft_worker is not None:
            fft_worker.stop()
        streamer = None
        data_handler = None
        fft_worker = None
        set_status(f"Could not start FLAC stream: {error}", "danger")


def stop_stream(_event: object) -> None:
    global data_handler, fft_worker, streamer

    _ = _event
    if streamer is not None:
        streamer.stopStream()
    if fft_worker is not None:
        fft_worker.stop()
    streamer = None
    data_handler = None
    fft_worker = None
    set_status("Stream stopped.", "light")

def start_pause_stream(_event: object):
    # global streamer
    _ = _event

    put(host_ip, "/WebXi/Applications/SLM?Action=StartPause")

    

def update_waveform() -> None:
    if data_handler is None:
        return

    samples = data_handler.snapshot()
    time_source.data = {
        "time": TIME_AXIS,
        "amplitude": samples[WAVEFORM_INDICES],
    }


def update_spectrum() -> None:
    if fft_worker is None:
        return

    frequency, levels = fft_worker.snapshot()
    frequency_source.data = {
        "frequency": frequency,
        "level": levels,
    }


start_button.on_click(start_stream)
stop_button.on_click(stop_stream)
start_pause.on_click(start_pause_stream)
pn.state.add_periodic_callback(update_waveform, period=50)
pn.state.add_periodic_callback(update_spectrum, period=50)

app = pn.Column(
    pn.pane.Markdown("# FLAC audio monitor"),
    pn.pane.Markdown(
        "FLAC streaming is available on supported SLM devices, including the 2255."
    ),
    pn.Row(host, start_button, stop_button, start_pause),
    status,
    pn.pane.Bokeh(time_plot),
    pn.pane.Bokeh(frequency_plot),
    sizing_mode="stretch_width",
)

app.servable()
