import math
import sys
import numpy as np
import pyqtgraph as pg
from rsxdwstreaming import xdw_streaming, odw

from PyQt6.QtCore import (
    QLocale,
)

from PyQt6.QtGui import (
    QDoubleValidator,
    QGuiApplication,
    QIntValidator,
)

from PyQt6.QtWidgets import (
    QMainWindow,
    QApplication,
    QWidget,
    QLabel,
    QCheckBox,
    QComboBox,
    QPushButton,
    QLineEdit,
    QGridLayout,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
)

# TODO:
# - Marker Support
# - Add status box with what ODWs are being sent


class XdwDemoGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = 'R&S ODW Demo GUI'
        self.left = 0
        self.top = 0
        self.width = 1500
        self.height = 700
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        resolution = QGuiApplication.primaryScreen().availableGeometry()
        self.move(int((resolution.width() - self.width) / 2), int((resolution.height() - self.height) / 2))

        self.tabs_widget = TabsWidget(self)
        self.setCentralWidget(self.tabs_widget)



class TabsWidget(QWidget):
    def __init__(self, parent):
        super(QWidget, self).__init__(parent)
        self.layout = QVBoxLayout(self)

        # Initialize tab screen
        self.tabs = QTabWidget()
        self.tab_single_odw = SingleOdwTab()
        self.tab_transient_odw = TransientOdwTab()

        # Add tabs
        self.tabs.addTab(self.tab_single_odw, "Single ODW")
        self.tabs.addTab(self.tab_transient_odw, "Transient ODW")

        # Add interface part
        self.xDWinterface = None
        self.xDWinterfaceIP = None
        self.xDWinterfacePort = None
        self.xDWinterfaceProtocol = None

        self.interfaceInfo = QWidget()
        interfaceInfoLayout = QHBoxLayout()
        self.l_ip = QLabel("IP:")
        self.le_ip = QLineEdit()
        self.le_ip.setFixedWidth(90)
        self.l_port = QLabel("Port:")
        self.le_port = QLineEdit()
        self.le_port.setFixedWidth(40)
        self.l_proto = QLabel("Protocol:")
        self.cb_proto = QComboBox()
        self.cb_proto.addItems(["TCP", "UDP"])
        # self.b_connect = QPushButton("Connect")
        # self.b_connect.clicked.connect(self.connect)
        # self.state = QLabel(self)
        # self.state.setFixedSize(20, 20)
        # self.state.setStyleSheet("background-color: red;")

        # interfaceInfoLayout.addWidget(self.l_interface_txt)
        interfaceInfoLayout.addWidget(self.l_ip)
        interfaceInfoLayout.addWidget(self.le_ip)
        interfaceInfoLayout.addWidget(self.l_port)
        interfaceInfoLayout.addWidget(self.le_port)
        interfaceInfoLayout.addWidget(self.l_proto)
        interfaceInfoLayout.addWidget(self.cb_proto)
        # interfaceInfoLayout.addWidget(self.b_connect)
        # interfaceInfoLayout.addWidget(self.state)

        self.interfaceInfo.setLayout(interfaceInfoLayout)

        # self.timer = QTimer(self)
        # self.timer.setInterval(500)          # Throw event timeout with an interval of 1000 milliseconds
        # self.timer.timeout.connect(self.get_state) # each time timer counts a second, call self.blink
        # self.connection_flag = False
        # self.timer.start()

        buttons = QWidget()
        hButtonsLayout = QHBoxLayout()
        self.b_clear = QPushButton("Set To Default")
        self.b_clear.clicked.connect(self.SetToDefault)
        self.b_send = QPushButton("Send ODW(s)")
        self.b_send.clicked.connect(self.sendxDW)
        # self.b_close = QPushButton("Close")
        # self.b_close.clicked.connect(self.exitApplication)

        hButtonsLayout.addWidget(self.b_clear)
        hButtonsLayout.addWidget(self.b_send)
        # hButtonsLayout.addWidget(self.b_close)
        buttons.setLayout(hButtonsLayout)

        # Add Qwidgets to widget
        self.layout.addWidget(self.tabs)
        self.layout.addWidget(self.interfaceInfo)
        self.layout.addWidget(buttons)

        self.setLayout(self.layout)
        self.le_ip.setText('192.168.1.61')
        self.le_port.setText('49152')

    # @pyqtSlot()
    # def get_state(self):
    #       if self.xDWinterface:
    #            self.xDWinterface.xdw_interface.recv(1)
    #            self.state.setStyleSheet("background-color: red;")
    #            self.state.setStyleSheet("background-color: green;")

    def connect(self):
        self.xDWinterfaceIP = self.le_ip.text()
        self.xDWinterfacePort = int(self.le_port.text())
        self.xDWinterfaceProtocol = self.cb_proto.currentText()
        try:
            self.xDWinterface = xdw_streaming.XdwStreaming(self.xDWinterfaceIP, self.xDWinterfacePort, self.xDWinterfaceProtocol)
        except ConnectionError:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("Could not connect!")
            msg.setWindowTitle("Connection Error")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
        else:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(f"Successfully connected to {self.le_ip.text()}!")
            msg.setWindowTitle("Connection successful")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()

    def SetToDefault(self):
        self.tabs.currentWidget().SetToDefault()

    def sendxDW(self):
        #todo: Loop for each numODW
        try:
            xDWinterfaceIP = self.le_ip.text()
            xDWinterfacePort = int(self.le_port.text())
            xDWinterfaceProtocol = self.cb_proto.currentText()
            xDWinterface = xdw_streaming.XdwStreaming(xDWinterfaceIP, xDWinterfacePort, xDWinterfaceProtocol)
            xDW = self.tabs.currentWidget().createXdw()
            xDWinterface.send_xdw(xDW)
        except ConnectionError:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("Could not send ODW!")
            msg.setWindowTitle("Parameter Error")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()

    # def exitApplication(self):
class SingleOdwTab(QWidget):
    def __init__(self, parent=None):
        super(SingleOdwTab, self).__init__(parent)

        self.loc_double_validation = QLocale("en")

        self.val_toa_expert = QDoubleValidator(0, ((1 << 52) - 1) / 2.4e9, 10)
        self.val_freq_offset = QDoubleValidator(-2.4e9 / 2, 2.4e9 * (1/2 - 1/(1 << 32)), 10)
        self.val_level_offset = QDoubleValidator(0, math.inf, 10)
        self.val_phase_offset = QDoubleValidator(0, 360 * (1 - 1/(1 << 16)), 10)
        self.val_segment = QIntValidator(0, (1 << 24) - 1)
        self.val_t_on25 = QDoubleValidator(0, ((1 << 25) - 1) / 2.4e9, 10)
        self.val_t_on44 = QDoubleValidator(0, ((1 << 44) - 1) / 2.4e9, 10)
        self.val_freq_inc = QDoubleValidator(-2.4e9, 2.4e9, 10)
        self.val_barker_code = QIntValidator(0, 8)

        self.loc_double_validation = QLocale("en")
        self.val_toa_expert.setLocale(self.loc_double_validation)
        self.val_freq_offset.setLocale(self.loc_double_validation)
        self.val_level_offset.setLocale(self.loc_double_validation)
        self.val_phase_offset.setLocale(self.loc_double_validation)
        self.val_segment.setLocale(self.loc_double_validation)
        self.val_t_on25.setLocale(self.loc_double_validation)
        self.val_t_on44.setLocale(self.loc_double_validation)
        self.val_freq_inc.setLocale(self.loc_double_validation)
        self.val_barker_code.setLocale(self.loc_double_validation)

        self.layout = QVBoxLayout()

        self.initWidgetCommon()

        self.layout.addWidget(self.widget_common)

        self.setLayout(self.layout)
        self.setWindowTitle("xDW streaming demo")
        self.bMode()
        self.SetToDefault()

    def initWidgetCommon(self):
        self.widget_common = QWidget()
        layout = QFormLayout()

        self.l_mode = QLabel("Use TOA Mode")
        self.cb_toa = QCheckBox()
        self.cb_toa.stateChanged.connect(self.bMode)
        self.l_toa = QLabel("TOA: [s]")
        self.le_toa = QLineEdit()
        self.l_freqoffset = QLabel("Frequency offset: [Hz]")
        self.le_freqoffset = QLineEdit()
        self.l_leveloffset = QLabel("Level offset (Attenuation): [dB] ")
        self.le_leveloffset = QLineEdit()
        self.l_phaseoffset = QLabel("Phase offset: [deg]")
        self.le_phaseoffset = QLineEdit()

        self.le_toa.setValidator(self.val_toa_expert)
        self.le_freqoffset.setValidator(self.val_freq_offset)
        self.le_leveloffset.setValidator(self.val_level_offset)
        self.le_phaseoffset.setValidator(self.val_phase_offset)


        layout.addRow(self.l_mode, self.cb_toa)
        layout.addRow(self.l_toa, self.le_toa)
        layout.addRow(self.l_freqoffset, self.le_freqoffset)
        layout.addRow(self.l_leveloffset, self.le_leveloffset)
        layout.addRow(self.l_phaseoffset, self.le_phaseoffset)
        self.widget_common.setLayout(layout)

    def bMode(self):
        self.le_toa.setEnabled(self.cb_toa.isChecked())

    def SetToDefault(self):
        self.cb_toa.setChecked(True)
        self.le_toa.setText('0.0')
        self.le_freqoffset.setText('0.0')
        self.le_leveloffset.setText('0.0')
        self.le_phaseoffset.setText('0.0')

    def checkInput(self, label, lineedit):
        if not lineedit.isEnabled() or lineedit.hasAcceptableInput():
            return True

        msg = QMessageBox()
        msg.setWindowTitle("Invalid Input Data")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(f"Please check the value for {label.text()} {lineedit.text()} to be in accordance to the ICD.")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

        return False

    def atof(self, lineedit):
        ret, ok = self.loc_double_validation.toDouble(lineedit.text())
        assert ok, f"Validation with QDoubleValidator succeeded but toDouble() failed (both using the same locale). " \
                   f"Problematic value: {lineedit.text()}"
        return ret

    def createXdw(self):
        toa = self.atof(self.le_toa)

        # Check all inputs valid (this has to be done manually, because doubles can be in state
        # QValidator::Intermediate, which is not valid as is but not blockable by the validator)
        inputsValid = True
        inputsValid = inputsValid & self.checkInput(self.l_toa, self.le_toa)
        inputsValid = inputsValid & self.checkInput(self.l_freqoffset, self.le_freqoffset)
        inputsValid = inputsValid & self.checkInput(self.l_leveloffset, self.le_leveloffset)
        inputsValid = inputsValid & self.checkInput(self.l_phaseoffset, self.le_phaseoffset)

        if not inputsValid:
            return

        level_offset = self.atof(self.le_leveloffset)
        freq_offset = self.atof(self.le_freqoffset)
        phase_offset = self.atof(self.le_phaseoffset)

        if self.cb_toa.isChecked():
            new_odw = odw.Odw(toa=toa, level_offset=level_offset, freq_offset=freq_offset, phase_offset=phase_offset)
        else:
            new_odw = odw.Odw(level_offset=level_offset, freq_offset=freq_offset, phase_offset=phase_offset)

        return new_odw.get_xdw()

class TransientOdwTab(QWidget):
    def __init__(self, parent=None):
        super(TransientOdwTab, self).__init__(parent)

        self.loc_double_validation = QLocale("en")

        self.val_toa_expert = QDoubleValidator(0, ((1 << 52) - 1) / 2.4e9, 10)
        self.val_num_toa = QIntValidator(0, (1 << 24) - 1)
        self.val_freq_offset = QDoubleValidator(-2.4e9 / 2, 2.4e9 * (1/2 - 1/(1 << 32)), 10)
        self.val_level_offset = QDoubleValidator(0, math.inf, 10)
        self.val_phase_offset = QDoubleValidator(0, 360 * (1 - 1/(1 << 16)), 10)
        self.val_segment = QIntValidator(0, (1 << 24) - 1)
        self.val_t_on25 = QDoubleValidator(0, ((1 << 25) - 1) / 2.4e9, 10)
        self.val_t_on44 = QDoubleValidator(0, ((1 << 44) - 1) / 2.4e9, 10)
        self.val_freq_inc = QDoubleValidator(-2.4e9, 2.4e9, 10)
        self.val_barker_code = QIntValidator(0, 8)

        self.loc_double_validation = QLocale("en")
        self.val_toa_expert.setLocale(self.loc_double_validation)
        self.val_num_toa.setLocale(self.loc_double_validation)
        self.val_freq_offset.setLocale(self.loc_double_validation)
        self.val_level_offset.setLocale(self.loc_double_validation)
        self.val_phase_offset.setLocale(self.loc_double_validation)
        self.val_segment.setLocale(self.loc_double_validation)
        self.val_t_on25.setLocale(self.loc_double_validation)
        self.val_t_on44.setLocale(self.loc_double_validation)
        self.val_freq_inc.setLocale(self.loc_double_validation)
        self.val_barker_code.setLocale(self.loc_double_validation)

        self.layout = QVBoxLayout()

        self.initWidgetCommon()

        self.layout.addWidget(self.widget_common)

        self.setLayout(self.layout)
        self.setWindowTitle("xDW streaming demo")
        #self.bMode()
        self.SetToDefault()

    def initWidgetCommon(self):
        self.widget_common = QWidget()
        layout = QFormLayout()

        #self.l_mode = QLabel("Use TOA Mode")
        #self.cb_toa = QCheckBox()
        #self.cb_toa.stateChanged.connect(self.bMode)
        self.ls_toa = QLabel("Start TOA: [s]")
        self.lse_toa = QLineEdit()
        self.le_toa = QLabel("End TOA: [s]")
        self.lee_toa = QLineEdit()
        self.ln_toa = QLabel("Number of TOAs")
        self.lne_toa = QLineEdit()
        self.l_freqoffset = QLabel("Frequency offset: [Hz]")
        self.le_freqoffset = QLineEdit()
        self.l_leveloffset = QLabel("Level offset (Attenuation): [dB] ")
        self.le_leveloffset = QLineEdit()
        self.ls_phaseoffset = QLabel("Phase offset start: [deg]")
        self.lse_phaseoffset = QLineEdit()
        self.le_phaseoffset = QLabel("Phase offset end: [deg]")
        self.lee_phaseoffset = QLineEdit()
        self.l_phaseprofile = QLabel("Phase Profile ")
        self.cb_phaseprofile = QComboBox()
        self.cb_phaseprofile.addItems(["None", "Ramp", "Parabolic", "Parabolic Peak", "Random"])
        self.cb_phaseprofile.currentIndexChanged.connect(self.selectPhaseProfile)
        self.toa_list = []
        self.phase_list = []

        self.lee_toa.setValidator(self.val_toa_expert)
        self.lse_toa.setValidator(self.val_toa_expert)
        self.lne_toa.setValidator(self.val_num_toa)
        self.le_freqoffset.setValidator(self.val_freq_offset)
        self.le_leveloffset.setValidator(self.val_level_offset)
        self.lee_phaseoffset.setValidator(self.val_phase_offset)
        self.lse_phaseoffset.setValidator(self.val_phase_offset)

        #layout.addRow(self.l_mode, self.cb_toa)
        layout.addRow(self.ls_toa, self.lse_toa)
        layout.addRow(self.le_toa, self.lee_toa)
        layout.addRow(self.ln_toa, self.lne_toa)
        layout.addRow(self.l_freqoffset, self.le_freqoffset)
        layout.addRow(self.l_leveloffset, self.le_leveloffset)
        #layout.addRow(self.l_phaseoffset, self.le_phaseoffset)
        layout.addRow(self.ls_phaseoffset, self.lse_phaseoffset)
        layout.addRow(self.le_phaseoffset, self.lee_phaseoffset)
        layout.addRow(self.l_phaseprofile, self.cb_phaseprofile)
        self.phase_plot = pg.PlotWidget()
        layout.addWidget(self.phase_plot)

        # Labels
        self.phase_plot.setLabel("bottom", "TOA")
        self.phase_plot.setLabel("left", "Phase", units="°")
        self.phase_plot.setTitle("Phase Profile")

        # Enable grid
        self.phase_plot.showGrid(x=True, y=True)

        self.widget_common.setLayout(layout)

    #def bMode(self):
    #    self.le_toa.setEnabled(self.cb_toa.isChecked())

    #def selectPhaseProfile(self):
    #    self.toa_list = np.linspace(start=float(self.lse_toa.text()), stop=float(self.lee_toa.text()), num=int(self.lne_toa.text()))
    #    print(f'TOAs: {self.toa_list}')
    #    if self.cb_phaseprofile.currentText() == "Ramp":
    #        print("Ramp phase")

    #        self.phase_list = np.linspace(start=float(self.lse_phaseoffset.text()), stop=float(self.lee_phaseoffset.text()), num=int(self.lne_toa.text()))
    #        print(self.phase_list)
    #    elif self.cb_phaseprofile.currentText() == "Parabolic":
    #        print("Parabolic phase")
    #        phase_start = float(self.lse_phaseoffset.text())
    #        phase_stop = float(self.lee_phaseoffset.text())
    #        self.phase_list = phase_start + (phase_stop - phase_start) * self.toa_list**2
    #        print(self.phase_list)
    def selectPhaseProfile(self):

        # Generate TOA values
        self.toa_list = np.linspace(
            start=float(self.lse_toa.text()),
            stop=float(self.lee_toa.text()),
            num=int(self.lne_toa.text())
        )

        print(f"TOAs: {self.toa_list}")

        phase_start = float(self.lse_phaseoffset.text())
        phase_stop = float(self.lee_phaseoffset.text())

        if self.cb_phaseprofile.currentText() == "Ramp":

            print("Ramp phase")

            self.phase_list = np.linspace(
                start=phase_start,
                stop=phase_stop,
                num=len(self.toa_list)
            )

        elif self.cb_phaseprofile.currentText() == "Parabolic":

            print("Parabolic phase")

            # Normalize TOA from 0 → 1
            x = (
                    (self.toa_list - self.toa_list[0])
                    / (self.toa_list[-1] - self.toa_list[0])
            )

            # Parabolic phase
            self.phase_list = (
                    phase_start
                    + (phase_stop - phase_start) * x ** 2
            )
        elif self.cb_phaseprofile.currentText() == "Parabolic Peak":

            phase_start = float(self.lse_phaseoffset.text())
            phase_stop = float(self.lee_phaseoffset.text())

            # Normalize TOA to 0 → 1
            x = (
                    (self.toa_list - self.toa_list[0])
                    / (self.toa_list[-1] - self.toa_list[0])
            )

            # Parabolic profile:
            # start = phase_start
            # middle = phase_stop
            # end = phase_start
            self.phase_list = (
                    phase_start
                    + (phase_stop - phase_start)
                    * (1 - (2 * x - 1) ** 2)
            )
        elif self.cb_phaseprofile.currentText() == "Random":

            self.phase_list = np.random.uniform(
                phase_start,
                phase_stop,
                len(self.toa_list)
            )
        print(f"Phase: {self.phase_list}")

        # Update plot
        self.phase_plot.clear()
        self.phase_plot.plot(
            self.toa_list,
            self.phase_list,
            pen=pg.mkPen("cyan", width=2),
            symbol="o",
            symbolSize=5
        )

    def SetToDefault(self):
        #self.cb_toa.setChecked(True)
        self.lse_toa.setText('0.0')
        self.lee_toa.setText('0.0')
        self.lne_toa.setText('1')
        self.le_freqoffset.setText('0.0')
        self.le_leveloffset.setText('0.0')
        self.lse_phaseoffset.setText('0.0')
        self.lee_phaseoffset.setText('0.0')
        self.cb_phaseprofile.setCurrentIndex(0)

    def checkInput(self, label, lineedit):
        if not lineedit.isEnabled() or lineedit.hasAcceptableInput():
            return True

        msg = QMessageBox()
        msg.setWindowTitle("Invalid Input Data")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(f"Please check the value for {label.text()} {lineedit.text()} to be in accordance to the ICD.")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

        return False

    def atof(self, lineedit):
        ret, ok = self.loc_double_validation.toDouble(lineedit.text())
        assert ok, f"Validation with QDoubleValidator succeeded but toDouble() failed (both using the same locale). " \
                   f"Problematic value: {lineedit.text()}"
        return ret

    def createXdw(self):
        #todo. Need to loop for each NumTOA to execute this. TOA will be passed from the method call
        toa = self.atof(self.lse_toa)

        # Check all inputs valid (this has to be done manually, because doubles can be in state
        # QValidator::Intermediate, which is not valid as is but not blockable by the validator)
        inputsValid = True
        inputsValid = inputsValid & self.checkInput(self.ls_toa, self.lse_toa)
        inputsValid = inputsValid & self.checkInput(self.l_freqoffset, self.le_freqoffset)
        inputsValid = inputsValid & self.checkInput(self.l_leveloffset, self.le_leveloffset)
        inputsValid = inputsValid & self.checkInput(self.ls_phaseoffset, self.lse_phaseoffset)
        inputsValid = inputsValid & self.checkInput(self.le_phaseoffset, self.lee_phaseoffset)

        if not inputsValid:
            return

        level_offset = self.atof(self.le_leveloffset)
        freq_offset = self.atof(self.le_freqoffset)
        phase_offset = self.atof(self.lse_phaseoffset)  #start phase offset for now. todo

        #if self.cb_toa.isChecked():
        new_odw = odw.Odw(toa=toa, level_offset=level_offset, freq_offset=freq_offset, phase_offset=phase_offset)
        #else:
        #    new_odw = odw.Odw(level_offset=level_offset, freq_offset=freq_offset, phase_offset=phase_offset)

        return new_odw.get_xdw()


def main():
    app = QApplication(sys.argv)
    ex = XdwDemoGui()
    ex.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
