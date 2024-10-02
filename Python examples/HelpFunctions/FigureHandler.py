import pyqtgraph as pg
import sys
import numpy as np
from PyQt5 import QtWidgets

from abc import ABC, abstractmethod

class FigureHandler(ABC):
    def __init__(self):
        self.i = 0
        self.chunkToShow = 2 ** 15
        self.fftSize = self.chunkToShow
        self.fftHamming = np.hamming(self.fftSize)
        # Used to store "old" spectrums for fft averaging
        self.old = 0
        self.oldold = 0

        self.x = np.linspace(0.0, 10, self.chunkToShow)

        ## Figures
        self.axis = np.arange(self.chunkToShow)
        self.axis = np.flip(self.axis * -1 / self.chunkToShow)
        self.x = np.zeros(len(self.axis))
        self.app = QtWidgets.QApplication(sys.argv)
        self.win = pg.GraphicsLayoutWidget(title="Streaming")
        self.win.setBackground('w')
        self.win.resize(1000, 600)
        self.plotTime = self.win.addPlot()
        self.curveTime = self.plotTime.plot(self.x, self.axis)
        self.curveTime.setPen(color='b', width=2, autoDownsample=True, clipToView=True)
        self.plotTime.showGrid(x=True, y=True)
        self.plotTime.setXRange(np.min(self.axis), np.max(self.axis))
        self.plotTime.setYRange(-2, 2)
        labelStyle = {'color': '#000', 'font-size': '13pt'}
        self.plotTime.getAxis('left').setStyle(tickFont=pg.QtGui.QFont('Arial', 11))
        self.plotTime.getAxis('bottom').setStyle(tickFont=pg.QtGui.QFont('Arial', 11))
        self.plotTime.getAxis('left').setLabel('Approximately pressure', units='Pa', **labelStyle)
        self.plotTime.getAxis('bottom').setLabel('Time', units='s', **labelStyle)

        # Subplot 2 (FFT)
        # Calculate the frequency vector
        self.win.nextRow()
        self.plotFreq = self.win.addPlot()
        freq = np.arange(self.fftSize//2 + 1) / (float(self.fftSize) / 32e3)
        self.curveFreq = self.plotFreq.plot(freq, np.arange(len(freq)))
        self.curveFreq.setPen(color='b', width=2, autoDownsample=True, clipToView=True)
        self.plotFreq.setXRange(0, np.max(freq))
        self.plotFreq.setYRange(-20, 130)
        self.plotFreq.getAxis('bottom').enableAutoSIPrefix(enable=False)
        self.plotFreq.setLogMode(x=True, y=False)
        self.plotFreq.showGrid(x=True, y=True)
        self.plotFreq.getAxis('left').setStyle(tickFont=pg.QtGui.QFont('Arial', 14))
        self.plotFreq.getAxis('bottom').setStyle(tickFont=pg.QtGui.QFont('Arial', 14))
        self.plotFreq.getAxis('left').setLabel('Approximately dB SPL re 20 µPa', **labelStyle)
        self.plotFreq.getAxis('bottom').setLabel('Frequency', units='Hz', **labelStyle)
        self.win.show()

        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(int(0.1 * 1000))

    def run(self):
        QtWidgets.QApplication.instance().exec_()

    @abstractmethod
    def update(self):
        pass

