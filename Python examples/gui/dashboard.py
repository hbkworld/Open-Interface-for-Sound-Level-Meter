from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import numpy as np
import panel as pn
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure

from slm_api.enums.sequence_id_enum import SequenceIdEnums
from slm_api.helpers import webxi_helper_functions as webxi_helper
from slm_api.helpers.data_handler import DataHandler
from slm_api.helpers.fft import dBfft
from slm_api.helpers.stream_handlers import WebXiStreamHandler

pn.extension()

HISTORY = 120
SAMPLE_RATE = 2**16
MP3_SAMPLE_RATE = 32_000
SAMPLE_COUNT = 2**16
FFT_SIZE = 2**15
WAVEFORM_POINTS = 2**11
FREQUENCY_LIMIT = 20_000
WAVEFORM_INDICES = np.linspace(0, SAMPLE_COUNT - 1, WAVEFORM_POINTS, dtype=np.intp)
FFT_WINDOW = np.hamming(FFT_SIZE)
COLORS = {"A": "#167d8d", "C": "#d26b40", "B": "#2600ff", "Z": "#7957a0"}
BB_METRICS = ("eq", "F", "Fmax", "Fmin", "S", "Smax", "Smin", "peak", "peak1s", "E")
BB_SEQUENCES = [
    name for weight in COLORS for metric in BB_METRICS
    if (name := f"L{weight}{metric}") in SequenceIdEnums.__members__
] + ["LAIeq", "LAImax", "LAFTeq"]
CPB_METRICS = ("eq", "F", "Fmax", "Fmin", "S", "Smax", "Smin")
CPB_SEQUENCES = [
    f"CPBL{weight}{metric}{suffix}"
    for weight in COLORS for metric in CPB_METRICS for suffix in ("", "2nd")
]


class BroadbandData(DataHandler):
    def __init__(self, names: list[str]) -> None:
        self.values = {name: deque([np.nan] * HISTORY, maxlen=HISTORY) for name in names}
        self.lock = threading.Lock()

    def handle(self, *, name: str, value: float, **_data: object) -> None:
        if name in self.values:
            with self.lock:
                self.values[name].append(float(value))

    def snapshot(self) -> dict[str, list[float]]:
        with self.lock:
            return {name: list(values) for name, values in self.values.items()}


class CPBData(DataHandler):
    def __init__(self) -> None:
        self.values = np.array([])
        self.lock = threading.Lock()

    def handle(self, *, value: object, **_data: object) -> None:
        with self.lock:
            self.values = np.asarray(value, dtype=float).copy()

    def snapshot(self) -> np.ndarray:
        with self.lock:
            return self.values.copy()


class AudioData(DataHandler):
    def __init__(self) -> None:
        self.samples = np.zeros(SAMPLE_COUNT * 2)
        self.next_index = 0
        self.size = 0
        self.lock = threading.Lock()
        self.new_data = threading.Event()

    def handle(self, *, samples: object, **_data: object) -> None:
        block = np.asarray(samples, dtype=float).reshape(-1)[-self.samples.size:]
        count = block.size
        if not count:
            return
        with self.lock:
            indices = (np.arange(count) + self.next_index) % self.samples.size
            self.samples[indices] = block
            self.next_index = (self.next_index + count) % self.samples.size
            self.size = min(self.size + count, self.samples.size)
        self.new_data.set()

    def snapshot(self) -> np.ndarray:
        with self.lock:
            result = np.zeros(SAMPLE_COUNT)
            count = min(self.size, SAMPLE_COUNT)
            if count == 0:
                return result
            result[-count:] = self.samples[
                (np.arange(count) + self.next_index - count) % self.samples.size
            ]
            return result


class SpectrumWorker:
    def __init__(self, data: AudioData, sample_rate: int) -> None:
        self.data = data
        self.sample_rate = sample_rate
        self.stopping = threading.Event()
        self.lock = threading.Lock()
        self.frequency = np.array([0.0])
        self.levels = np.array([0.0])
        self.thread = threading.Thread(target=self.run, daemon=True, name="dashboard-fft")

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stopping.set()
        self.data.new_data.set()
        self.thread.join(timeout=2)

    def run(self) -> None:
        while not self.stopping.is_set():
            if not self.data.new_data.wait(0.15):
                continue
            self.data.new_data.clear()
            if self.stopping.is_set():
                break
            frequency, levels = dBfft(
                self.data.snapshot()[-FFT_SIZE:], self.sample_rate, FFT_WINDOW, ref=20e-6
            )
            limit = min(len(frequency), int(FREQUENCY_LIMIT * FFT_SIZE / self.sample_rate) + 1)
            frequency, levels = frequency[:limit], levels[:limit]
            edges = np.linspace(0, limit, min(512, limit) + 1, dtype=np.intp)
            with self.lock:
                self.frequency = np.array([frequency[a:b].mean() for a, b in zip(edges[:-1], edges[1:])])
                self.levels = np.array([levels[a:b].max() for a, b in zip(edges[:-1], edges[1:])])

    def snapshot(self) -> tuple[np.ndarray, np.ndarray]:
        with self.lock:
            return self.frequency.copy(), self.levels.copy()


def default_host() -> str:
    path = Path(__file__).resolve().parents[1] / "slm_ip"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def build_dashboard() -> pn.Column:
    host = pn.widgets.TextInput(name="SLM host", value=default_host())
    bb_values = pn.widgets.MultiChoice(name="Broadband measurements", options=BB_SEQUENCES,
                                        value=["LAeq", "LCeq"])
    cpb_value = pn.widgets.Select(name="CPB measurement", options=["Off", *CPB_SEQUENCES], value="Off")
    flac = pn.widgets.Checkbox(name="FLAC waveform and spectrum", value=False)
    mp3 = pn.widgets.Checkbox(name="MP3 waveform and spectrum", value=False)
    start = pn.widgets.Button(name="Start selected", button_type="primary")
    stop = pn.widgets.Button(name="Stop all", button_type="light")
    status = pn.pane.Alert("Streams stopped.", alert_type="light")
    plots = pn.Column(sizing_mode="stretch_width")
    streams: list[WebXiStreamHandler] = []
    workers: list[SpectrumWorker] = []
    updates: list[Callable[[], None]] = []

    def set_status(message: str, kind: str = "light") -> None:
        status.object = message
        status.alert_type = kind

    def stop_streams(_event: object = None) -> None:
        for stream in streams:
            stream.stopStream()
        streams.clear()
        for worker in workers:
            worker.stop()
        workers.clear()
        updates.clear()
        plots.clear()
        set_status("Streams stopped.")

    def start_streams(_event: object) -> None:
        address = host.value.strip()
        selected = list(bb_values.value)
        cpb_name = cpb_value.value
        if not address:
            set_status("Enter an SLM host.", "warning")
            return
        if not (selected or cpb_name != "Off" or flac.value or mp3.value):
            set_status("Select at least one stream.", "warning")
            return
        try:
            stop_streams()
            if selected:
                webxi_helper.turn_off_bb_freq_weight(address)
                webxi_helper.turn_on_bb_freq_weight(address, sorted({name[1] for name in selected}))
                webxi_helper.turn_on_bb_leq(address, selected)
                data = BroadbandData(selected)
                stream = WebXiStreamHandler(
                    address, sequenceNames=selected, mode="multi",
                    streamName=f"Dashboard-BB-{uuid4().hex}",
                )
                streams.append(stream)
                stream.setDataHandler(data)
                source = ColumnDataSource(data={"x": list(range(HISTORY)), **data.snapshot()})
                chart = figure(title="Broadband levels", height=300, sizing_mode="stretch_width",
                               x_axis_label="Samples", y_axis_label="Level [dB SPL]", y_range=(0, 120))
                for name in selected:
                    chart.line("x", name, source=source, color=COLORS[name[1]], line_width=2, legend_label=name)
                chart.legend.click_policy = "hide"
                plots.append(pn.pane.Bokeh(chart))

                def update_bb(data=data, source=source) -> None:
                    source.data = {"x": list(range(HISTORY)), **data.snapshot()}

                updates.append(update_bb)

            if cpb_name != "Off":
                band = cpb_name[4]
                webxi_helper.turn_off_CPB_freq_weight(address)
                webxi_helper.turn_on_CPB_freq_weight(
                    address, band + ("2nd" if cpb_name.endswith("2nd") else "")
                )
                webxi_helper.turn_on_cpb_leq(address, cpb_name)
                data_cpb = CPBData()
                stream = WebXiStreamHandler(
                    address, sequenceNames=[cpb_name], mode="cpb",
                    streamName=f"Dashboard-CPB-{uuid4().hex}",
                )
                streams.append(stream)
                stream.setDataHandler(data_cpb)
                bands = stream.calcFreqBands()
                widths = [frequency * 0.2 for frequency in bands]
                source_cpb = ColumnDataSource(data={
                    "frequency": bands, "level": [0.0] * len(bands), "width": widths,
                })
                chart = figure(title=f"{cpb_name} spectrum", height=300, sizing_mode="stretch_width",
                               x_axis_label="Frequency band [Hz]", y_axis_label="Level [dB SPL]",
                               x_axis_type="log", y_range=(0, 120))
                chart.vbar(x="frequency", top="level", bottom=0, width="width",
                           source=source_cpb, color=COLORS[band])
                plots.append(pn.pane.Bokeh(chart))

                def update_cpb(data=data_cpb, source=source_cpb, bands=bands, widths=widths) -> None:
                    levels = data.snapshot()
                    if levels.size == len(bands):
                        source.data = {"frequency": bands, "level": levels, "width": widths}

                updates.append(update_cpb)

            for enabled, mode, sequence_id, sample_rate in (
                (flac.value, "flac", SequenceIdEnums.FLACSignal.value, SAMPLE_RATE),
                (mp3.value, "mp3", SequenceIdEnums.MP3Signal.value, MP3_SAMPLE_RATE),
            ):
                if not enabled:
                    continue
                data_audio = AudioData()
                stream = WebXiStreamHandler(
                    address, mode=mode, sequenceID=sequence_id,
                    streamName=f"Dashboard-{mode.upper()}-{uuid4().hex}",
                )
                streams.append(stream)
                stream.setDataHandler(data_audio)
                fft_worker = SpectrumWorker(data_audio, sample_rate)
                fft_worker.start()
                workers.append(fft_worker)
                time_axis = np.arange(WAVEFORM_POINTS) * SAMPLE_COUNT / (sample_rate * WAVEFORM_POINTS)
                waveform_source = ColumnDataSource(data={"time": time_axis, "amplitude": np.zeros(WAVEFORM_POINTS)})
                spectrum_source = ColumnDataSource(data={"frequency": [0.0], "level": [0.0]})
                waveform = figure(title=f"{mode.upper()} waveform", height=300, sizing_mode="stretch_width",
                                  x_axis_label="Time [s]", y_axis_label="Pressure [Pa]")
                waveform.line("time", "amplitude", source=waveform_source, line_width=1)
                spectrum = figure(title=f"{mode.upper()} spectrum", height=300, sizing_mode="stretch_width",
                                  x_axis_label="Frequency [Hz]", y_axis_label="dB SPL re 20 uPa",
                                  x_range=(0, min(FREQUENCY_LIMIT, sample_rate / 2)))
                spectrum.line("frequency", "level", source=spectrum_source, line_width=2)
                plots.extend([pn.pane.Bokeh(waveform), pn.pane.Bokeh(spectrum)])

                def update_audio(data=data_audio, fft=fft_worker, time_axis=time_axis,
                                 waveform_source=waveform_source, spectrum_source=spectrum_source) -> None:
                    waveform_source.data = {"time": time_axis, "amplitude": data.snapshot()[WAVEFORM_INDICES]}
                    frequency, levels = fft.snapshot()
                    spectrum_source.data = {"frequency": frequency, "level": levels}

                updates.append(update_audio)

            for stream in streams:
                threading.Thread(target=stream.startStream, daemon=True,
                                 name=f"dashboard-{stream.mode}").start()
            set_status("Streaming selected data.", "success")
        except Exception as error:
            try:
                stop_streams()
            except Exception:
                pass
            set_status(f"Could not start streams: {error}", "danger")

    def refresh() -> None:
        for update in updates:
            update()

    start.on_click(start_streams)
    stop.on_click(stop_streams)
    pn.state.add_periodic_callback(refresh, period=50)
    return pn.Column(
        pn.pane.Markdown("# Sound level dashboard"),
        pn.FlexBox(host, bb_values, cpb_value, flac, mp3, flex_wrap="wrap"),
        pn.Row(start, stop), status, plots, sizing_mode="stretch_width",
    )


build_dashboard().servable()