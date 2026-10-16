from __future__ import annotations

import threading
from collections import deque
from pathlib import Path

import numpy as np
import panel as pn
import requests
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure

from slm_api.helpers import webxi_helper_functions as webxi_helper
from slm_api.helpers.data_handler import DataHandler
from slm_api.helpers.stream_handlers import WebXiStreamHandler

pn.extension()

WEIGHT_TO_SEQUENCE = {
    "A": "LAeq",
    "C": "LCeq",
    "Z": "LZeq",
}
BUFFER_SIZE = 120


class PlotDataHandler(DataHandler):
    """Keep the most recent broadband values for the Bokeh document."""

    def __init__(self, sequence_names: list[str]) -> None:
        self.values = {
            name: deque([np.nan] * BUFFER_SIZE, maxlen=BUFFER_SIZE)
            for name in sequence_names
        }
        self.lock = threading.Lock()

    def handle(self, *, name: str, value: float, **_data: object) -> None:
        if name not in self.values:
            return
        with self.lock:
            self.values[name].append(float(value))

    def snapshot(self) -> dict[str, list[float]]:
        with self.lock:
            return {name: list(values) for name, values in self.values.items()}


def read_default_host() -> str:
    host_file = Path(__file__).resolve().parents[1] / "slm_ip"
    return host_file.read_text(encoding="utf-8").strip() if host_file.exists() else ""


weights = pn.widgets.MultiChoice(
    name="BB frequency weightings",
    options=list(WEIGHT_TO_SEQUENCE),
    value=["A", "C"],
    max_items=3,
)
host = pn.widgets.TextInput(name="SLM host", value=read_default_host())
start_button = pn.widgets.Button(name="Start stream", button_type="primary")
stop_button = pn.widgets.Button(name="Stop stream", button_type="light")
status = pn.pane.Alert("Stream stopped.", alert_type="light")

plot = figure(
    title="Broadband sound level",
    height=500,
    sizing_mode="stretch_width",
    x_axis_label="Samples",
    y_axis_label="Level [dB SPL]",
    y_range=(0, 120),
)
source = ColumnDataSource(
    data={"x": list(range(BUFFER_SIZE)), **{
        sequence: [np.nan] * BUFFER_SIZE
        for sequence in WEIGHT_TO_SEQUENCE.values()
    }}
)
renderers = {
    sequence: plot.line(
        x="x",
        y=sequence,
        source=source,
        line_width=2,
        legend_label=weight,
        visible=weight in weights.value,
    )
    for weight, sequence in WEIGHT_TO_SEQUENCE.items()
}
plot.legend.location = "top_left"
plot.legend.click_policy = "hide"

streamer: WebXiStreamHandler | None = None
data_handler: PlotDataHandler | None = None
stream_thread: threading.Thread | None = None


def set_status(message: str, alert_type: str = "light") -> None:
    status.object = message
    status.alert_type = alert_type


def update_visible_lines(_event: object) -> None:
    selected = set(weights.value)
    for weight, renderer in renderers.items():
        renderer.visible = weight in selected


def start_stream(_event: object) -> None:
    global data_handler, streamer, stream_thread

    if not host.value.strip():
        set_status("Enter the SLM host before starting the stream.", "warning")
        return
    if not weights.value:
        set_status("Select at least one BB frequency weighting.", "warning")
        return

    stop_stream(None)
    selected_weights = list(weights.value)
    sequence_names = [WEIGHT_TO_SEQUENCE[weight] for weight in selected_weights]

    try:
        webxi_helper.turn_off_bb_freq_weight(host.value.strip())
        webxi_helper.turn_on_bb_freq_weight(host.value.strip(), selected_weights)
        webxi_helper.turn_on_bb_leq(host.value.strip(), sequence_names)
        data_handler = PlotDataHandler(sequence_names)
        streamer = WebXiStreamHandler(
            host.value.strip(),
            sequenceNames=sequence_names,
            mode="multi",
        )
        streamer.setDataHandler(data_handler)
        stream_thread = threading.Thread(
            target=streamer.startStream,
            name="slm-stream",
            daemon=True,
        )
        stream_thread.start()
        set_status(f"Streaming {', '.join(selected_weights)} weighting(s).", "success")
    except (OSError, ValueError, RuntimeError, requests.RequestException) as error:
        streamer = None
        data_handler = None
        set_status(f"Could not start stream: {error}", "danger")


def stop_stream(_event: object) -> None:
    global streamer, data_handler, stream_thread

    if streamer is not None:
        streamer.stopStream()
    streamer = None
    data_handler = None
    stream_thread = None
    set_status("Stream stopped.", "light")


def update_plot() -> None:
    if data_handler is None:
        return
    snapshot = data_handler.snapshot()
    for sequence, values in snapshot.items():
        source.data[sequence] = values


weights.param.watch(update_visible_lines, "value")
start_button.on_click(start_stream)
stop_button.on_click(stop_stream)
pn.state.add_periodic_callback(update_plot, period=500)

app = pn.Column(
    pn.pane.Markdown("# Broadband sound-level monitor"),
    pn.Row(host, weights),
    pn.Row(start_button, stop_button),
    status,
    pn.pane.Bokeh(plot),
    sizing_mode="stretch_width",
)

app.servable()
