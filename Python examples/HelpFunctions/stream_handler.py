import requests
from requests.auth import HTTPDigestAuth

def setup_stream(host,ip,sequenceID,StreamName):
    """Initilize a stream and start it. Returns the URI for the stream"""

    # This line checks if only one sequenceID is given and converts it to a list. Otherwise it will keep the list given
    sequenceID = [sequenceID] if isinstance(sequenceID, int) else sequenceID

    body = {
                "ConnectionType": "WebSocket",
                "Sequences": sequenceID,
                "MessageTypes": ["SequenceData"],
                "Name": StreamName
            }
    response = requests.post(host + "/WebXi/Streams", json = body)
    print(response)
    if not (response.status_code == 201):  
        print(response.text)
        raise Exception("Cannot start stream, could be bacause of to many streams open on the device")
    return 'ws://' + ip + response.json()["URI"][0]

def get_stream_ID(host, streamName):
    """This function shows how to find the ID of a specific stream with specific name"""
    streams = requests.get(host + "/WebXi/Streams?recursive").json()
    # The keys are the stream IDs and are not renumbered when a stream is deleted
    matches = [int(ID) for ID, subtree in streams.items() if subtree["Name"] == streamName]
    return max(matches) if matches else None

def delete_stream(host, streamName):
    """Look up a stream by name and delete it, cleaning up the device resources used"""
    streamID = get_stream_ID(host, streamName)
    if streamID is not None:
        response = requests.delete(host + "/WebXi/Streams/" + str(streamID), timeout=10)
        response.raise_for_status()

def data_type_conv(data_type, value, vector_length):
    """Convert the byte data retrived from BK2245 to Int16 format\n
       The byte format is in 'little'"""
    if data_type == "Int16":
        if vector_length == None:
            return int.from_bytes(value, "little", signed=True)
        else:
            value_array = []
            for i in range(0, vector_length*2, 2):
                value_array.append(int.from_bytes(value[i:i+2], "little", signed=True))
            # print(len(value_array))
            return value_array
    elif data_type == "BKTimeSpan":
        return int.from_bytes(value[-4:], "little", signed=True)