import requests

# Functions to turn on/off BB freq weights and sequences. These are used in the examples to make sure the wanted sequences are enabled on the SLM.
def turn_off_bb_freq_weight(host):
    requests.put(host + "/webxi/Applications/SLM/Setup/BBFreqWeightB", json=False)
    requests.put(host + "/webxi/Applications/SLM/Setup/BBFreqWeightZ", json=False)
    requests.put(host + "/webxi/Applications/SLM/Setup/BBFreqWeightA", json=False)
    requests.put(host + "/webxi/Applications/SLM/Setup/BBFreqWeightC", json=False)

def turn_on_bb_freq_weight(host, weights):
    for weight in weights:
        requests.put(host + f"/webxi/Applications/SLM/Setup/BBFreqWeight{weight}", json=True)

def turn_on_bbl_eq(host, weights):
    for weight in weights:
        requests.put(host + f"/webxi/Applications/SLM/Setup/BB{weight}", json=True)


def turn_off_CPB_freq_weight(host):
    requests.put(host + "/webxi/Applications/SLM/Setup/CPBFreqWeightB", json=False)
    requests.put(host + "/webxi/Applications/SLM/Setup/CPBFreqWeightZ", json=False)
    requests.put(host + "/webxi/Applications/SLM/Setup/CPBFreqWeightA", json=False)
    requests.put(host + "/webxi/Applications/SLM/Setup/CPBFreqWeightC", json=False)

def turn_on_CPB_freq_weight(host, weights):
    for weight in weights:
        requests.put(host + f"/webxi/Applications/SLM/Setup/CPBFreqWeight{weight}", json=True)

def turn_on_CPB_l_eq(host, weights):
    for weight in weights:
        requests.put(host + f"/webxi/Applications/SLM/Setup/CPB{weight}", json=True)