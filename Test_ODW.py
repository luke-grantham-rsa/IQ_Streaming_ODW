import csv
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
    QFileDialog,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
)

# TODO:
# - Marker Support
# - Add status box with what ODWs are being sent

# ICD-derived bounds (see the bit-packing in rsxdwstreaming's odw.py/xdw.py), used to flag
# out-of-range values in an imported CSV before they would fail to encode at send time.
TOA_MAX_S = ((1 << 52) - 1) / 2.4e9
FREQ_OFFSET_MIN_HZ = -2.4e9 / 2
FREQ_OFFSET_MAX_HZ = 2.4e9 * (1 / 2 - 1 / (1 << 32))
LEVEL_OFFSET_MIN_DB = 0
PHASE_OFFSET_MIN_DEG = 0
PHASE_OFFSET_MAX_DEG = 360 * (1 - 1 / (1 << 16))


def build_toa_plot(name, unit, plot_unit=None):
    """Builds a styled, empty TOA-vs-value pyqtgraph plot, shared by the Transient
    (generated) and Import (loaded from CSV) tabs."""
    plot = pg.PlotWidget()
    plot.setBackground("w")
    plot.setMinimumHeight(250)
    plot.setLabel("bottom", "TOA")
    plot.setLabel("left", name, units=plot_unit if plot_unit is not None else unit)
    plot.setTitle(f"{name} Profile")
    plot.showGrid(x=True, y=True)
    return plot


def plot_toa_profile(plot, toa_list, value_list):
    plot.clear()
    plot.plot(
        toa_list,
        value_list,
        pen=pg.mkPen("b", width=2),
        symbol="o",
        symbolSize=5
    )


MAX_PATHS = 8
DEFAULT_PATHS = 2


class XdwDemoGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.title = 'R&S ODW Demo GUI'
        self.left = 0
        self.top = 0
        self.width = 1500
        self.height = 740
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        resolution = QGuiApplication.primaryScreen().availableGeometry()
        self.move(int((resolution.width() - self.width) / 2), int((resolution.height() - self.height) / 2))

        # Each Path tab is a fully independent TabsWidget - its own IP/Port/Protocol and
        # its own Single/Transient/Import ODW state - so different profiles can be loaded
        # onto different SMWs at once. Starts with DEFAULT_PATHS tabs plus a Chrome-style
        # "+" tab that appends another Path (up to MAX_PATHS) when clicked.
        self.instrument_tabs = QTabWidget()
        self.tabs_widgets = []
        for _ in range(DEFAULT_PATHS):
            self.addPathTab()
        self.instrument_tabs.setCurrentIndex(0)

        self.plus_tab_widget = QWidget()
        self.instrument_tabs.addTab(self.plus_tab_widget, "+")
        self.instrument_tabs.tabBarClicked.connect(self.handleTabBarClicked)

        self.setCentralWidget(self.instrument_tabs)

    def addPathTab(self):
        if len(self.tabs_widgets) >= MAX_PATHS:
            return

        tabs_widget = TabsWidget(None)
        self.tabs_widgets.append(tabs_widget)

        # Insert before the "+" tab, if it still exists (not present during initial setup)
        plus_index = self.instrument_tabs.indexOf(self.plus_tab_widget) if hasattr(self, 'plus_tab_widget') else -1
        insert_index = plus_index if plus_index != -1 else self.instrument_tabs.count()
        self.instrument_tabs.insertTab(insert_index, tabs_widget, f"Path {len(self.tabs_widgets)}")
        self.instrument_tabs.setCurrentIndex(insert_index)

        if len(self.tabs_widgets) >= MAX_PATHS and hasattr(self, 'plus_tab_widget'):
            self.instrument_tabs.removeTab(self.instrument_tabs.indexOf(self.plus_tab_widget))

    def handleTabBarClicked(self, index):
        if self.instrument_tabs.widget(index) is self.plus_tab_widget:
            self.addPathTab()



class TabsWidget(QWidget):
    def __init__(self, parent):
        super(QWidget, self).__init__(parent)
        self.layout = QVBoxLayout(self)

        # Initialize tab screen
        self.tabs = QTabWidget()
        self.tab_single_odw = SingleOdwTab()
        self.tab_transient_odw = TransientOdwTab()
        self.tab_import_odw = ImportOdwTab()

        # Add tabs
        self.tabs.addTab(self.tab_single_odw, "Single ODW")
        self.tabs.addTab(self.tab_transient_odw, "Transient ODW")
        self.tabs.addTab(self.tab_import_odw, "Import")

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
        self.le_port.setFixedWidth(60)
        self.l_proto = QLabel("Protocol:")
        self.cb_proto = QComboBox()
        self.cb_proto.addItems(["TCP", "UDP"])
        self.cb_proto.setFixedWidth(70)
        # self.b_connect = QPushButton("Connect")
        # self.b_connect.clicked.connect(self.connect)
        # self.state = QLabel(self)
        # self.state.setFixedSize(20, 20)
        # self.state.setStyleSheet("background-color: red;")

        # interfaceInfoLayout.addWidget(self.l_interface_txt)
        interfaceInfoLayout.addWidget(self.l_ip)
        interfaceInfoLayout.addWidget(self.le_ip)
        interfaceInfoLayout.addSpacing(20)
        interfaceInfoLayout.addWidget(self.l_port)
        interfaceInfoLayout.addWidget(self.le_port)
        interfaceInfoLayout.addSpacing(20)
        interfaceInfoLayout.addWidget(self.l_proto)
        interfaceInfoLayout.addWidget(self.cb_proto)
        # interfaceInfoLayout.addWidget(self.b_connect)
        # interfaceInfoLayout.addWidget(self.state)
        interfaceInfoLayout.addStretch(1)

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
        self.b_export = QPushButton("Export All Profiles to CSV")
        self.b_export.clicked.connect(self.exportCsv)
        # self.b_close = QPushButton("Close")
        # self.b_close.clicked.connect(self.exitApplication)

        hButtonsLayout.addWidget(self.b_clear)
        hButtonsLayout.addWidget(self.b_send)
        hButtonsLayout.addWidget(self.b_export)
        # hButtonsLayout.addWidget(self.b_close)
        buttons.setLayout(hButtonsLayout)

        # Export only makes sense for the Transient ODW tab's TOA-vs-value profiles
        self.tabs.currentChanged.connect(self.updateExportEnabled)
        self.updateExportEnabled(self.tabs.currentIndex())

        # Add Qwidgets to widget
        self.layout.addWidget(self.tabs)
        self.layout.addWidget(self.interfaceInfo)
        self.layout.addWidget(buttons)

        self.setLayout(self.layout)
        self.le_ip.setText('192.168.1.231')
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

    def updateExportEnabled(self, index):
        # Export applies to any tab that holds a TOA-indexed profile (Transient, Import) -
        # not the single-ODW tab, which has no list to export.
        self.b_export.setEnabled(index != 0)

    def exportCsv(self):
        self.tabs.currentWidget().exportCsv()

    def sendxDW(self):
        try:
            xDWinterfaceIP = self.le_ip.text()
            xDWinterfacePort = int(self.le_port.text())
            xDWinterfaceProtocol = self.cb_proto.currentText()
            xDWinterface = xdw_streaming.XdwStreaming(xDWinterfaceIP, xDWinterfacePort, xDWinterfaceProtocol)
            current_tab = self.tabs.currentWidget()
            print(f'Sending ODWs from tab {self.tabs.currentIndex()}')
            if self.tabs.currentIndex() == 0:
                xDW = current_tab.createXdw()
                xDWinterface.send_xdw(xDW)
            else:
                # Transient (generated) and Import (loaded from CSV) tabs both expose a
                # TOA-indexed list of ODW parameters and are sent the same way.
                if hasattr(current_tab, 'refreshAllProfiles'):
                    current_tab.refreshAllProfiles()
                for index, toa in enumerate(current_tab.toa_list):
                    xDW = current_tab.createXdw(
                        toa,
                        current_tab.freq_list[index],
                        current_tab.amp_list[index],
                        current_tab.phase_list[index],
                    )
                    xDWinterface.send_xdw(xDW)
            print(f'ODWs sent to instrument at {self.le_ip.text()}')
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

    PROFILE_NAMES = ["None", "Ramp", "Parabolic", "Parabolic Peak", "Random"]

    def initWidgetCommon(self):
        self.widget_common = QWidget()
        outer_layout = QVBoxLayout()

        toa_widget = QWidget()
        toa_layout = QFormLayout()

        #self.l_mode = QLabel("Use TOA Mode")
        #self.cb_toa = QCheckBox()
        #self.cb_toa.stateChanged.connect(self.bMode)
        self.ls_toa = QLabel("Start TOA: [s]")
        self.lse_toa = QLineEdit()
        self.le_toa = QLabel("End TOA: [s]")
        self.lee_toa = QLineEdit()
        self.ln_toa = QLabel("Number of TOAs")
        self.lne_toa = QLineEdit()

        self.lee_toa.setValidator(self.val_toa_expert)
        self.lse_toa.setValidator(self.val_toa_expert)
        self.lne_toa.setValidator(self.val_num_toa)

        #toa_layout.addRow(self.l_mode, self.cb_toa)
        toa_layout.addRow(self.ls_toa, self.lse_toa)
        toa_layout.addRow(self.le_toa, self.lee_toa)
        toa_layout.addRow(self.ln_toa, self.lne_toa)
        toa_widget.setLayout(toa_layout)
        outer_layout.addWidget(toa_widget)

        self.toa_list = []

        self.profile_tabs = QTabWidget()

        freq_tab, (self.l_freqstart, self.le_freqstart, self.l_freqend, self.le_freqend,
                   self.l_freqprofile, self.cb_freqprofile, self.freq_plot) = self.buildProfileTab(
            "Frequency offset", "Hz", self.val_freq_offset, self.selectFrequencyProfile,
            profile_label="Frequency"
        )
        self.profile_tabs.addTab(freq_tab, "Frequency")
        self.freq_list = []

        amp_tab, (self.l_ampstart, self.le_ampstart, self.l_ampend, self.le_ampend,
                  self.l_ampprofile, self.cb_ampprofile, self.amp_plot) = self.buildProfileTab(
            "Level offset (Attenuation)", "dB", self.val_level_offset, self.selectAmplitudeProfile,
            profile_label="Amplitude"
        )
        self.profile_tabs.addTab(amp_tab, "Amplitude")
        self.amp_list = []

        phase_tab, (self.ls_phaseoffset, self.lse_phaseoffset, self.le_phaseoffset, self.lee_phaseoffset,
                    self.l_phaseprofile, self.cb_phaseprofile, self.phase_plot) = self.buildProfileTab(
            "Phase offset", "deg", self.val_phase_offset, self.selectPhaseProfile,
            plot_unit="°", profile_label="Phase"
        )
        self.profile_tabs.addTab(phase_tab, "Phase")
        self.phase_list = []

        outer_layout.addWidget(self.profile_tabs)

        self.widget_common.setLayout(outer_layout)

    def buildProfileTab(self, name, unit, validator, on_profile_changed, plot_unit=None, profile_label=None):
        """Builds a sub-tab with Start/End/Profile fields plus a live TOA-vs-value plot for
        one quantity, matching the pattern already established for phase offset."""
        tab = QWidget()
        layout = QFormLayout()

        l_start = QLabel(f"{name} start: [{unit}]")
        le_start = QLineEdit()
        le_start.setValidator(validator)

        l_end = QLabel(f"{name} end: [{unit}]")
        le_end = QLineEdit()
        le_end.setValidator(validator)

        l_profile = QLabel(f"{profile_label if profile_label is not None else name} Profile ")
        cb_profile = QComboBox()
        cb_profile.addItems(self.PROFILE_NAMES)
        cb_profile.currentIndexChanged.connect(on_profile_changed)

        layout.addRow(l_start, le_start)
        layout.addRow(l_end, le_end)
        layout.addRow(l_profile, cb_profile)

        plot = build_toa_plot(name, unit, plot_unit)
        layout.addWidget(plot)

        tab.setLayout(layout)

        return tab, (l_start, le_start, l_end, le_end, l_profile, cb_profile, plot)

    #def bMode(self):
    #    self.le_toa.setEnabled(self.cb_toa.isChecked())

    def generateToaList(self):
        return np.linspace(
            start=float(self.lse_toa.text()),
            stop=float(self.lee_toa.text()),
            num=int(self.lne_toa.text())
        )

    @staticmethod
    def computeProfile(profile_name, start, stop, toa_list):
        if profile_name == "Ramp":
            return np.linspace(start=start, stop=stop, num=len(toa_list))

        elif profile_name == "Parabolic":
            # Normalize TOA from 0 → 1
            x = (toa_list - toa_list[0]) / (toa_list[-1] - toa_list[0])
            return start + (stop - start) * x ** 2

        elif profile_name == "Parabolic Peak":
            # Normalize TOA from 0 → 1; profile rises from start to stop at the
            # midpoint and back down to start at the end
            x = (toa_list - toa_list[0]) / (toa_list[-1] - toa_list[0])
            return start + (stop - start) * (1 - (2 * x - 1) ** 2)

        elif profile_name == "Random":
            return np.random.uniform(start, stop, len(toa_list))

        else:  # "None"
            return np.full(len(toa_list), start)

    def selectFrequencyProfile(self):
        self.toa_list = self.generateToaList()
        self.freq_list = self.computeProfile(
            self.cb_freqprofile.currentText(),
            float(self.le_freqstart.text()),
            float(self.le_freqend.text()),
            self.toa_list
        )
        print(f"Frequency offsets: {self.freq_list}")
        plot_toa_profile(self.freq_plot, self.toa_list, self.freq_list)

    def selectAmplitudeProfile(self):
        self.toa_list = self.generateToaList()
        self.amp_list = self.computeProfile(
            self.cb_ampprofile.currentText(),
            float(self.le_ampstart.text()),
            float(self.le_ampend.text()),
            self.toa_list
        )
        print(f"Level offsets: {self.amp_list}")
        plot_toa_profile(self.amp_plot, self.toa_list, self.amp_list)

    def selectPhaseProfile(self):
        self.toa_list = self.generateToaList()
        self.phase_list = self.computeProfile(
            self.cb_phaseprofile.currentText(),
            float(self.lse_phaseoffset.text()),
            float(self.lee_phaseoffset.text()),
            self.toa_list
        )
        print(f"Phase: {self.phase_list}")
        plot_toa_profile(self.phase_plot, self.toa_list, self.phase_list)

    def refreshAllProfiles(self):
        """Recomputes all three profiles from the current field values so the lists sent
        to the instrument always match, even if the user never touched every combobox."""
        self.selectFrequencyProfile()
        self.selectAmplitudeProfile()
        self.selectPhaseProfile()

    def exportCsv(self):
        self.refreshAllProfiles()

        path, _ = QFileDialog.getSaveFileName(self, "Export ODW Profile", "odw_profile.csv", "CSV Files (*.csv)")
        if not path:
            return

        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["TOA [s]", "Frequency Offset [Hz]", "Level Offset [dB]", "Phase Offset [deg]"])
            for toa, freq_offset, level_offset, phase_offset in zip(
                    self.toa_list, self.freq_list, self.amp_list, self.phase_list):
                writer.writerow([toa, freq_offset, level_offset, phase_offset])

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(f"Exported {len(self.toa_list)} ODW(s) to {path}")
        msg.setWindowTitle("Export Complete")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def SetToDefault(self):
        #self.cb_toa.setChecked(True)
        self.lse_toa.setText('0.0')
        self.lee_toa.setText('0.0')
        self.lne_toa.setText('1')
        self.le_freqstart.setText('0.0')
        self.le_freqend.setText('0.0')
        self.le_ampstart.setText('0.0')
        self.le_ampend.setText('0.0')
        self.lse_phaseoffset.setText('0.0')
        self.lee_phaseoffset.setText('0.0')
        self.cb_freqprofile.setCurrentIndex(0)
        self.cb_ampprofile.setCurrentIndex(0)
        self.cb_phaseprofile.setCurrentIndex(0)
        self.refreshAllProfiles()

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

    def createXdw(self, toa, freq_offset, level_offset, phase_offset):
        print(f'generating ODW with TOA: {toa}, freq: {freq_offset}, level: {level_offset}, phase: {phase_offset}')
        # Check all inputs valid (this has to be done manually, because doubles can be in state
        # QValidator::Intermediate, which is not valid as is but not blockable by the validator)
        inputsValid = True
        inputsValid = inputsValid & self.checkInput(self.ls_toa, self.lse_toa)
        inputsValid = inputsValid & self.checkInput(self.le_toa, self.lee_toa)
        inputsValid = inputsValid & self.checkInput(self.l_freqstart, self.le_freqstart)
        inputsValid = inputsValid & self.checkInput(self.l_freqend, self.le_freqend)
        inputsValid = inputsValid & self.checkInput(self.l_ampstart, self.le_ampstart)
        inputsValid = inputsValid & self.checkInput(self.l_ampend, self.le_ampend)
        inputsValid = inputsValid & self.checkInput(self.ls_phaseoffset, self.lse_phaseoffset)
        inputsValid = inputsValid & self.checkInput(self.le_phaseoffset, self.lee_phaseoffset)

        if not inputsValid:
            return

        new_odw = odw.Odw(toa=toa, level_offset=level_offset, freq_offset=freq_offset, phase_offset=phase_offset)

        return new_odw.get_xdw()


class ImportOdwTab(QWidget):
    """Loads a TOA-indexed ODW profile from a CSV (matching the format produced by
    TransientOdwTab.exportCsv) and plots it, without needing to regenerate it from a
    Start/End/Profile shape."""

    def __init__(self, parent=None):
        super(ImportOdwTab, self).__init__(parent)

        self.toa_list = np.array([])
        self.freq_list = np.array([])
        self.amp_list = np.array([])
        self.phase_list = np.array([])

        self.layout = QVBoxLayout()

        self.b_import = QPushButton("Import CSV")
        self.b_import.clicked.connect(self.importCsv)
        self.layout.addWidget(self.b_import)

        self.l_status = QLabel("No profile loaded.")
        self.layout.addWidget(self.l_status)

        plots_layout = QHBoxLayout()

        self.freq_plot = build_toa_plot("Frequency offset", "Hz")
        self.freq_plot.setMinimumHeight(300)
        plots_layout.addWidget(self.freq_plot)

        self.amp_plot = build_toa_plot("Level offset (Attenuation)", "dB")
        self.amp_plot.setMinimumHeight(300)
        plots_layout.addWidget(self.amp_plot)

        self.phase_plot = build_toa_plot("Phase offset", "deg", plot_unit="°")
        self.phase_plot.setMinimumHeight(300)
        plots_layout.addWidget(self.phase_plot)

        self.layout.addLayout(plots_layout)

        self.setLayout(self.layout)
        self.setWindowTitle("xDW streaming demo")

    def importCsv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import ODW Profile", "", "CSV Files (*.csv)")
        if not path:
            return

        toa_list, freq_list, amp_list, phase_list = [], [], [], []
        try:
            with open(path, newline='') as f:
                reader = csv.reader(f)
                next(reader)  # header row
                for row in reader:
                    toa, freq_offset, level_offset, phase_offset = (float(v) for v in row)
                    toa_list.append(toa)
                    freq_list.append(freq_offset)
                    amp_list.append(level_offset)
                    phase_list.append(phase_offset)
        except (OSError, csv.Error, ValueError, StopIteration) as e:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText(f"Could not import '{path}':\n{e}")
            msg.setWindowTitle("Import Error")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            return

        self.toa_list = np.array(toa_list)
        self.freq_list = np.array(freq_list)
        self.amp_list = np.array(amp_list)
        self.phase_list = np.array(phase_list)

        plot_toa_profile(self.freq_plot, self.toa_list, self.freq_list)
        plot_toa_profile(self.amp_plot, self.toa_list, self.amp_list)
        plot_toa_profile(self.phase_plot, self.toa_list, self.phase_list)

        out_of_range = self.checkRanges()
        if out_of_range:
            self.l_status.setText(
                f"Loaded {len(self.toa_list)} ODW(s) from {path} - "
                f"WARNING: {', '.join(out_of_range)} out of ICD range, sending may fail."
            )
        else:
            self.l_status.setText(f"Loaded {len(self.toa_list)} ODW(s) from {path}")

    def checkRanges(self):
        """Returns the names of any columns with values outside the ICD-derived bounds."""
        out_of_range = []
        if self.toa_list.size and (np.any(self.toa_list < 0) or np.any(self.toa_list > TOA_MAX_S)):
            out_of_range.append("TOA")
        if self.freq_list.size and (np.any(self.freq_list < FREQ_OFFSET_MIN_HZ) or np.any(self.freq_list > FREQ_OFFSET_MAX_HZ)):
            out_of_range.append("Frequency offset")
        if self.amp_list.size and np.any(self.amp_list < LEVEL_OFFSET_MIN_DB):
            out_of_range.append("Level offset")
        if self.phase_list.size and (np.any(self.phase_list < PHASE_OFFSET_MIN_DEG) or np.any(self.phase_list > PHASE_OFFSET_MAX_DEG)):
            out_of_range.append("Phase offset")
        return out_of_range

    def SetToDefault(self):
        self.toa_list = np.array([])
        self.freq_list = np.array([])
        self.amp_list = np.array([])
        self.phase_list = np.array([])
        self.l_status.setText("No profile loaded.")
        self.freq_plot.clear()
        self.amp_plot.clear()
        self.phase_plot.clear()

    def exportCsv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export ODW Profile", "odw_profile.csv", "CSV Files (*.csv)")
        if not path:
            return

        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["TOA [s]", "Frequency Offset [Hz]", "Level Offset [dB]", "Phase Offset [deg]"])
            for toa, freq_offset, level_offset, phase_offset in zip(
                    self.toa_list, self.freq_list, self.amp_list, self.phase_list):
                writer.writerow([toa, freq_offset, level_offset, phase_offset])

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(f"Exported {len(self.toa_list)} ODW(s) to {path}")
        msg.setWindowTitle("Export Complete")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def createXdw(self, toa, freq_offset, level_offset, phase_offset):
        new_odw = odw.Odw(toa=toa, level_offset=level_offset, freq_offset=freq_offset, phase_offset=phase_offset)
        return new_odw.get_xdw()


def main():
    app = QApplication(sys.argv)
    ex = XdwDemoGui()
    ex.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
