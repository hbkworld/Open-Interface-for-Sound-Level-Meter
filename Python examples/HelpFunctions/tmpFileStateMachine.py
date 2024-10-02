import enum
import tempfile

# a dual bufferfile stores the data which is used for decoding the mp3 stream.
class TmpfileStateMachine:
    # tmpfiles are used to store the mp3 data which are used for decoding.
    class State(enum.Enum):
        init = 0
        file1 = 1
        preFile2 = 2
        file2 = 3
        preFile1 = 4

    def __init__(self):
        self.tempFile1 = None
        self.tempFile2 = None
        self.state = self.State.init

    def runStateMachine(self, mp3Data):
        readData = None
        match self.state:
            case self.State.init:
                readData = self.on_init(mp3Data)
            case self.State.file1:
                readData = self.on_file1(mp3Data)
            case self.State.preFile2:
                readData = self.on_preFile2(mp3Data)
            case self.State.file2:
                readData = self.on_file2(mp3Data)
            case self.State.preFile1:
                readData = self.on_preFile1(mp3Data)
        return readData

    def on_init(self, mp3Data):
        if not self.tempFile1:
            self.tempFile1 = tempfile.SpooledTemporaryFile(max_size=1 * 1024 * 1024, mode='w+b', suffix=".mp3",
                                                           prefix="tmp1")
        self.tempFile1.write(bytes(mp3Data))
        self.tempFile1.seek(0)
        dataFromFile = self.tempFile1.read()
        if (len(dataFromFile) > 20 * 1024):
            self.state = self.State.preFile2
        return dataFromFile

    def on_file1(self, mp3Data):
        if self.tempFile2:
            self.tempFile2.close()
            self.tempFile2 = None
        self.tempFile1.seek(0)
        dataFromFile = self.tempFile1.read()
        self.tempFile1.write(bytes(mp3Data))
        if (len(dataFromFile) > 20 * 1024):
            self.state = self.State.preFile2
        return dataFromFile

    def on_preFile2(self, mp3Data):
        if not self.tempFile2:
            self.tempFile2 = tempfile.SpooledTemporaryFile(max_size=1 * 1024 * 1024, mode='w+b', suffix=".mp3",
                                                           prefix="tmp2")
        self.tempFile1.seek(0)
        self.tempFile2.seek(0)
        dataFromFile = self.tempFile1.read()
        tmp = self.tempFile2.read()
        self.tempFile1.write(bytes(mp3Data))
        self.tempFile2.write(bytes(mp3Data))
        if (len(dataFromFile) > 30 * 1024):
            self.state = self.State.file2
        return dataFromFile

    def on_file2(self, mp3Data):
        if self.tempFile1:
            self.tempFile1.close()
            self.tempFile1 = None
        self.tempFile2.seek(0)
        dataFromFile = self.tempFile2.read()
        self.tempFile2.write(bytes(mp3Data))
        if (len(dataFromFile) > 20 * 1024):
            self.state = self.State.preFile1
        return dataFromFile

    def on_preFile1(self, mp3Data):
        if not self.tempFile1:
            self.tempFile1 = tempfile.SpooledTemporaryFile(max_size=1 * 1024 * 1024, mode='w+b', suffix=".mp3",
                                                           prefix="tmp1")
        self.tempFile1.seek(0)
        self.tempFile2.seek(0)
        dataFromFile = self.tempFile2.read()
        tmp = self.tempFile1.read()
        self.tempFile1.write(bytes(mp3Data))
        self.tempFile2.write(bytes(mp3Data))
        if (len(dataFromFile) > 30 * 1024):
            self.state = self.State.file1
        return dataFromFile
