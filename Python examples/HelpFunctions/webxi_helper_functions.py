import requests
from dotenv import load_dotenv
import os

# Reuse one connection to the device instead of opening a new TCP connection per
# request — some devices take multiple seconds to accept a brand-new connection.
_session = requests.Session()

# Functions to turn on/off BB freq weights and sequences. These are used in the examples to make sure the wanted sequences are enabled on the SLM.
def turn_off_bb_freq_weight(host):
    for endpoint in (
        "/webxi/Applications/SLM/Setup/BBFreqWeightB",
        "/webxi/Applications/SLM/Setup/BBFreqWeightZ",
        "/webxi/Applications/SLM/Setup/BBFreqWeightA",
        "/webxi/Applications/SLM/Setup/BBFreqWeightC",
    ):
        response = _session.put(host + endpoint, json=False, timeout=10)
        response.raise_for_status()

def turn_on_bb_freq_weight(host, weights):
    for weight in weights:
        _session.put(host + f"/webxi/Applications/SLM/Setup/BBFreqWeight{weight}", json=True)

def turn_on_bb_leq(host, weights):
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

def turn_on_cpb_leq(host, weights):
    for weight in weights:
        _session.put(host + f"/webxi/Applications/SLM/Setup/CPB{weight}", json=True)

def set_host_ip(caller_file):
    env_path = os.path.join(os.path.dirname(caller_file), ".env")
    load_dotenv(dotenv_path=env_path)
    ip = os.getenv("IP")
    if not ip:
        # First run (or missing IP): ask once and persist it to .env for next time
        ip = input("No IP found. Enter the IP address of your SLM: ").strip()
        if not ip:
            raise RuntimeError('Missing IP. Set IP in a .env file (IP=...) or environment variable.')
        with open(env_path, "a") as f:
            f.write(f"IP={ip}\n")
    return f"http://{ip}", ip