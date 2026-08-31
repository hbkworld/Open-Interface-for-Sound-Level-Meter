import requests
from dotenv import load_dotenv
import os

# Reuse one connection to the device instead of opening a new TCP connection per
# request — some devices take multiple seconds to accept a brand-new connection.
_session = requests.Session()

# Functions to turn on/off BB freq weights and sequences. These are used in the examples to make sure the wanted sequences are enabled on the SLM.
def turn_off_bb_freq_weight(host):
    _session.put(host + "/webxi/Applications/SLM/Setup/BBFreqWeightB", json=False)
    _session.put(host + "/webxi/Applications/SLM/Setup/BBFreqWeightZ", json=False)
    _session.put(host + "/webxi/Applications/SLM/Setup/BBFreqWeightA", json=False)
    _session.put(host + "/webxi/Applications/SLM/Setup/BBFreqWeightC", json=False)

def turn_on_bb_freq_weight(host, weights):
    for weight in weights:
        _session.put(host + f"/webxi/Applications/SLM/Setup/BBFreqWeight{weight}", json=True)

def turn_on_bbl_eq(host, weights):
    for weight in weights:
        _session.put(host + f"/webxi/Applications/SLM/Setup/BB{weight}", json=True)


def turn_off_CPB_freq_weight(host):
    _session.put(host + "/webxi/Applications/SLM/Setup/CPBFreqWeightB", json=False)
    _session.put(host + "/webxi/Applications/SLM/Setup/CPBFreqWeightZ", json=False)
    _session.put(host + "/webxi/Applications/SLM/Setup/CPBFreqWeightA", json=False)
    _session.put(host + "/webxi/Applications/SLM/Setup/CPBFreqWeightC", json=False)

def turn_on_CPB_freq_weight(host, weights):
    for weight in weights:
        _session.put(host + f"/webxi/Applications/SLM/Setup/CPBFreqWeight{weight}", json=True)

def turn_on_CPB_l_eq(host, weights):
    for weight in weights:
        _session.put(host + f"/webxi/Applications/SLM/Setup/CPB{weight}", json=True)

def set_host_ip(caller_file):
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(caller_file), ".env"))
    ip = os.getenv("IP")
    if not ip:
        raise RuntimeError('Missing IP. Set IP in a .env file (IP=...) or environment variable.')
    return f"http://{ip}", ip