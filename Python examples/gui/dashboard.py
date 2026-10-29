"""
To run the gui 
$ panel serve .\gui\dashboard.py --show in therminal
"""


from __future__ import annotations

import datetime
import threading
from collections import deque
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import numpy as np
import panel as pn
from bokeh.models import ColumnDataSource, CustomJS, HoverTool
from bokeh.plotting import figure

from slm_api.enums.sequence_id_enum import SequenceIdEnums
from slm_api.helpers import webxi_helper_functions as webxi_helper
from slm_api.helpers.data_handler import DataHandler
from slm_api.helpers.fft import dBfft
from slm_api.helpers.stream_handlers import WebXiStreamHandler
from slm_api.helpers.webxi_helper_functions import set_host
from slm_api.helpers.https_requests import get, put

pn.extension("gridstack")



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
GRAPH_PANEL_HEIGHT = 400


def prioritize_hover(plot):
    plot.js_on_change(
        "inner_width",
        CustomJS(
            args={"toolbar": plot.toolbar},
            code="""
                if (toolbar.buttons === "auto") {
                    const tools = [...toolbar.tools].sort(
                        (first, second) =>
                            Number(second.type === "HoverTool") -
                            Number(first.type === "HoverTool"),
                    );
                    toolbar.buttons = tools.map(tool => tool.tool_button());
                }
            """,
        ),
    )

    



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
    path = set_host()
    return path

def freq_values(host, letter):
    to_capital = letter.upper()
    freq = get(host, "/WebXi?recursive").json()

    freq_bool = freq["Applications"]["SLM"]["Setup"][f"BBFreqWeight{to_capital}"]
    return freq_bool

def get_bb_values(host):
    webxi_values = get(host, "/WebXi?recursive").json()
    setup = webxi_values["Applications"]["SLM"]["Setup"]

    return [
        name.removeprefix("BB")
        for name in setup
        if name.startswith("BBL")
        and setup[f"BBFreqWeight{name[3].upper()}"]
    ]
    
def get_cpb_values(host):
        webxi_values = get(host, "/WebXi?recursive").json()
        setup = webxi_values["Applications"]["SLM"]["Setup"]
        cpb_values = []
        for name in setup:
            if name.startswith("CPBL"):
                cpb_values.append(name)

        return cpb_values

class SafeGridStack(pn.layout.GridStack):
    @pn.depends("state", watch=True)
    def _update_objects(self):
        current_ids = {str(id(obj)) for obj in self}
        incoming_ids = {item["id"] for item in self.state}

        if incoming_ids != current_ids:
            return

        super()._update_objects()

def build_dashboard() -> pn.Column:
    
    
    host = pn.widgets.TextInput(name="SLM host", value=default_host())
    BB_SEQUENCES = get_bb_values(host.value)
    CPB_SEQUENCES = get_cpb_values(host.value)

    choose_bb_frequencies = pn.widgets.MultiChoice(name="Select BB frequencies", options=["A", "B", "C", "Z"], max_items=3)
    enable_bb_frequencies = pn.widgets.Button(name="Enable selected BB frequencies", button_type="primary")
    pause_measurement = pn.widgets.Button(name="Start/Pause measurement", button_type="primary" )
    bb_values = pn.widgets.MultiChoice(name="Broadband measurements", options=BB_SEQUENCES)
    cpb_value = pn.widgets.MultiChoice(name="CPB measurements", options=CPB_SEQUENCES, value=[])
    flac = pn.widgets.Checkbox(name="FLAC waveform and spectrum", value=False)
    mp3 = pn.widgets.Checkbox(name="MP3 waveform and spectrum", value=False)
    start = pn.widgets.Button(name="Start selected", button_type="primary")
    stop = pn.widgets.Button(name="Stop all", button_type="light")
    status = pn.pane.Alert("Streams stopped.", alert_type="light")
    # plots = pn.Column(sizing_mode="stretch_width")
    plots = SafeGridStack(
    ncols=12,
    height=GRAPH_PANEL_HEIGHT,
    sizing_mode="stretch_width",
    allow_drag=False,
    allow_resize=False,
)
    rearrange = pn.widgets.Switch(name="Rearrange graphs", value=False)
    rearrange.link(plots, value="allow_drag")
    streams: list[WebXiStreamHandler] = []
    workers: list[SpectrumWorker] = []
    updates: list[Callable[[], None]] = []
    save_streams = pn.widgets.MultiChoice(name="Save streams", options=["BB", "CPB"])
    save_flac = pn.widgets.Toggle(name="Save FLAC", value=False, button_type="light")
    save_mp3 = pn.widgets.Toggle(name="Save MP3", value=False, button_type="light")
    save_format = pn.widgets.Select(name="BB / CPB file format", options=["json", "csv"], value="json")
    file_name = pn.widgets.TextInput(name="Filename", value="name-of-file")
    save_timestamps = pn.widgets.Checkbox(name="Include timestamps", value=True)
    folder_picker = pn.widgets.FileSelector(
        name="Destination folder", directory=str(Path(__file__).resolve().parents[1]),
        only_files=False,
    )

    def add_plot(chart):
        row = len(plots.objects)
        plots.height = (row + 1) * GRAPH_PANEL_HEIGHT
        plots[row:row + 1, 0:12] = pn.Column(
            pn.pane.Markdown(
                f"**{chart.title.text}**",
                styles={"cursor": "grab"},
            ),
            pn.pane.Bokeh(chart),
            sizing_mode="stretch_width",
        )

    def update_save_button(event: object) -> None:
        button = event.obj
        button.button_type = "success" if event.new else "light"

    save_flac.param.watch(update_save_button, "value")
    save_mp3.param.watch(update_save_button, "value")

    def set_status(message: str, kind: str = "light") -> None:
        status.object = message
        status.alert_type = kind

    def start_pause_measurement(event):
        put(host.value, "/WebXi/Applications/SLM?Action=StartPause")


    pause_measurement.on_click(start_pause_measurement)


    def activate_bb_frequencies(event):
        address = host.value.strip()
        selected = list(choose_bb_frequencies.value)

        if not address or not selected:
            set_status("Enter a host and select BB frequencies.", "warning")
            return

        try:
            webxi_helper.turn_off_bb_freq_weight(address)
            webxi_helper.turn_on_bb_freq_weight(address, selected)

            allowed = get_bb_values(address)
            bb_values.value = [
                name for name in bb_values.value if name in allowed
            ]
            bb_values.options = allowed

            set_status(f"Enabled BB weights: {', '.join(selected)}", "success")
        except Exception as error:
            set_status(f"Could not enable BB weights: {error}", "danger")

    enable_bb_frequencies.on_click(activate_bb_frequencies)

    def stop_streams(_event: object = None) -> None:
        for stream in streams:
            stream.stopStream()
        streams.clear()
        for worker in workers:
            worker.stop()
        workers.clear()
        updates.clear()
        # plots.clear()
        plots.objects = {}
        plots.height = GRAPH_PANEL_HEIGHT
        set_status("Streams stopped.")

    def start_streams(_event: object) -> None:
        address = host.value.strip()
        selected = list(bb_values.value)
        cpb_names = list(cpb_value.value)
        if not address:
            set_status("Enter an SLM host.", "warning")
            return
        if not (selected or cpb_names or flac.value or mp3.value):
            set_status("Select at least one stream.", "warning")
            return
        cpb_primary = {name[4] for name in cpb_names if not name.endswith("2nd")}
        cpb_secondary = {name[4] for name in cpb_names if name.endswith("2nd")}
        if len(cpb_primary) > 1 or len(cpb_secondary) > 1:
            set_status("Select only one frequency weighting per CPB slot; use the second slot for another weighting.", "warning")
            return
        active_types = {label for label, enabled in (
            ("BB", bool(selected)), ("CPB", bool(cpb_names)),
            ("FLAC", flac.value), ("MP3", mp3.value),
        ) if enabled}
        saved_types = set(save_streams.value) & active_types
        if save_flac.value and flac.value:
            saved_types.add("FLAC")
        if save_mp3.value and mp3.value:
            saved_types.add("MP3")
        destination = None
        if saved_types:
            if len(folder_picker.value) != 1 or not Path(folder_picker.value[0]).is_dir():
                set_status("Select exactly one destination folder for saved data.", "warning")
                return
            destination = Path(folder_picker.value[0])
            prefix = file_name.value.strip()
            if (not prefix or prefix in {".", ".."}
                    or any(character in '<>:"/\\|?*' or ord(character) < 32 for character in prefix)
                    or prefix.endswith((".", " "))):
                set_status("Enter a valid filename without a path or extension.", "warning")
                return
        filename = f'{file_name.value.strip()}_{datetime.datetime.now().strftime("%H%M_%m%d%Y")}'

        def saving_options(stream_type: str) -> dict[str, str]:
            save_type = "CPB" if stream_type.startswith("CPBL") else stream_type
            if save_type not in saved_types or destination is None:
                return {}
            extension = "wav" if stream_type in {"FLAC", "MP3"} else save_format.value
            stem = f"{filename}_{stream_type}"
            candidate = stem
            counter = 2
            while ((destination / f"{candidate}.{extension}").exists()
                   or any(destination.glob(f"{candidate}_fullscale-*.wav"))):
                candidate = f"{stem}_{counter}"
                counter += 1
            return {"save_format": extension, "save_path": str(destination / candidate)}

        try:
            stop_streams()
            if selected:
                webxi_helper.turn_on_bb_leq(address, selected)
                data = BroadbandData(selected)
                stream = WebXiStreamHandler(
                    address, sequenceNames=selected, mode="multi",
                    streamName=f"Dashboard-BB-{uuid4().hex}",
                    **saving_options("BB"), time=save_timestamps.value,
                )
                streams.append(stream)
                stream.setDataHandler(data)
                source = ColumnDataSource(data={"x": list(range(HISTORY)), **data.snapshot()})
                chart = figure(title="Broadband levels", height=300, sizing_mode="stretch_width",
                               x_axis_label="Samples", y_axis_label="Level [dB SPL]", y_range=(0, 120))
                for name in selected:
                    chart.line("x", name, source=source, color=COLORS[name[1]], line_width=2, legend_label=name, name=name)
                chart.add_tools(HoverTool(
                    renderers=[chart.renderers[0]],
                    tooltips=[
                        ("Sample", "@x{0}"),
                        *[
                            (name, f"@{{{name}}}{{0.00}} dB")
                            for name in selected
                        ],
                    ],
                    mode="vline",
                ))
                chart.legend.click_policy = "hide"
                chart.toolbar.active_inspect = None
                prioritize_hover(chart)
                # plots.append(pn.pane.Bokeh(chart))
                add_plot(chart)

                def update_bb(data=data, source=source) -> None:
                    source.data = {"x": list(range(HISTORY)), **data.snapshot()}

                updates.append(update_bb)

            if cpb_names:
                setup = get(address, "/WebXi?recursive").json()["Applications"]["SLM"]["Setup"]
                current_primary = {letter for letter in COLORS if setup.get(f"CPBFreqWeight{letter}", False)}
                current_secondary = {letter for letter in COLORS if setup.get(f"CPBFreqWeight{letter}2nd", False)}
                desired_primary = cpb_primary or current_primary
                desired_secondary = cpb_secondary or current_secondary
                if cpb_secondary and not desired_primary:
                    raise ValueError("Select a primary CPB measurement before using the second slot.")
                primary_changed = desired_primary != current_primary
                secondary_changed = desired_secondary != current_secondary
                if primary_changed or secondary_changed:
                    for letter in current_secondary:
                        put(address, f"/webxi/Applications/SLM/Setup/CPBFreqWeight{letter}2nd", json=False)
                if primary_changed:
                    for letter in current_primary:
                        put(address, f"/webxi/Applications/SLM/Setup/CPBFreqWeight{letter}", json=False)
                    for letter in desired_primary:
                        webxi_helper.turn_on_CPB_freq_weight(address, letter)
                if primary_changed or secondary_changed:
                    for letter in desired_secondary:
                        webxi_helper.turn_on_CPB_freq_weight(address, f"{letter}2nd")

            for cpb_name in cpb_names:
                band = cpb_name[4]
                webxi_helper.turn_on_cpb_leq(address, cpb_name)
                data_cpb = CPBData()
                stream = WebXiStreamHandler(
                    address, sequenceNames=[cpb_name], mode="cpb",
                    streamName=f"Dashboard-CPB-{uuid4().hex}",
                    **saving_options(cpb_name), time=save_timestamps.value,
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
                chart.add_tools(HoverTool(
                    tooltips=[
                        ("Frequency", "@frequency{0.0} Hz"),
                        ("Level", "@level{0.00} dB"),
                    ],
                    mode="vline",
                ))
                chart.toolbar.active_inspect = None
                prioritize_hover(chart)
                # plots.append(pn.pane.Bokeh(chart))
                add_plot(chart)

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
                    **saving_options(mode.upper()),
                )
                streams.append(stream)
                stream.setDataHandler(data_audio)
                fft_worker = SpectrumWorker(data_audio, sample_rate)
                fft_worker.start()
                workers.append(fft_worker)
                time_axis = np.arange(WAVEFORM_POINTS) * SAMPLE_COUNT / (sample_rate * WAVEFORM_POINTS)
                waveform_source = ColumnDataSource(data={
                    "time": time_axis,
                    "amplitude": np.zeros(WAVEFORM_POINTS),
                })
                spectrum_source = ColumnDataSource(data={
                    "frequency": [0.0],
                    "level": [0.0],
                })
                waveform = figure(
                    title=f"{mode.upper()} waveform",
                    height=300,
                    sizing_mode="stretch_width",
                    x_axis_label="Time [s]",
                    y_axis_label="Pressure [Pa]",
                    x_range=(0, SAMPLE_COUNT / sample_rate),
                    y_range=(-1, 1),
                )
                waveform.line(
                    "time", "amplitude",
                    source=waveform_source,
                    line_width=1,
                )

                spectrum = figure(
                    title=f"{mode.upper()} spectrum",
                    height=300,
                    sizing_mode="stretch_width",
                    x_axis_label="Frequency [Hz]",
                    y_axis_label="dB SPL re 20 uPa",
                    x_range=(0, min(FREQUENCY_LIMIT, sample_rate / 2)),
                    y_range=(0, 120),
                )
                spectrum.line(
                    "frequency", "level",
                    source=spectrum_source,
                    line_width=2,
                )
                waveform.add_tools(HoverTool(
                    tooltips=[
                        ("Time", "@time{0.000} s"),
                        ("Pressure", "@amplitude{0.00000} Pa"),
                    ],
                    mode="vline",
                ))

                spectrum.add_tools(HoverTool(
                    tooltips=[
                        ("Frequency", "@frequency{0.0} Hz"),
                        ("Level", "@level{0.00} dB"),
                    ],
                    mode="vline",
                ))
                waveform.toolbar.active_inspect = None
                spectrum.toolbar.active_inspect = None
                for plot in (waveform, spectrum):
                    prioritize_hover(plot)
                # plots.extend([pn.pane.Bokeh(waveform), pn.pane.Bokeh(spectrum)])
                add_plot(waveform)
                add_plot(spectrum)

                def update_audio(data=data_audio, fft=fft_worker, time_axis=time_axis,
                    waveform_source=waveform_source, spectrum_source=spectrum_source) -> None:
                    waveform_source.data = {"time": time_axis, "amplitude": data.snapshot()[WAVEFORM_INDICES]}
                    frequency, levels = fft.snapshot()
                    spectrum_source.data = {"frequency": frequency, "level": levels}

                updates.append(update_audio)

            for stream in streams:
                threading.Thread(target=stream.startStream, daemon=True,
                                 name=f"dashboard-{stream.mode}").start()
            message = "Streaming selected data."
            if saved_types:
                message += f" Saving {', '.join(sorted(saved_types))} to {destination}."
            set_status(message, "success")
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

    broadband_controls = pn.Column(
        "### Broadband",
        choose_bb_frequencies,
        enable_bb_frequencies,
        bb_values,
        sizing_mode="stretch_width",
    )

    cpb_controls = pn.Column(
        "### CPB",
        cpb_value,
        sizing_mode="stretch_width",
    )

    audio_controls = pn.Column(
        "### Audio",
        flac,
        save_flac,
        mp3,
        save_mp3,
        sizing_mode="stretch_width",
    )

    recording_controls = pn.Column(
        "### Recording",
        save_streams,
        save_format,
        file_name,
        save_timestamps,
        pn.Accordion(
            ("Destination folder", folder_picker),
            active=[],
        ),
        sizing_mode="stretch_width",
    )
    controls = pn.Column(
        host,
        pause_measurement,        
        pn.Row(rearrange),
        pn.layout.Divider(),
        broadband_controls,
        cpb_controls,
        audio_controls,
        pn.layout.Divider(),
        recording_controls,
        pn.Row(start, stop),
        status,
        sizing_mode="stretch_width",
        styles={"flex": "1 1 400px", "min-width": "0"},
    )

    plots.styles = {"flex": "2 1 640px", "min-width": "0"}

    return pn.Column(
        "# Sound level dashboard",
        pn.FlexBox(
            controls,
            plots,
            flex_wrap="wrap",
            align_items="flex-start",
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
    )


build_dashboard().servable()