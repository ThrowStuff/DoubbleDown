# SPDX-License-Identifier: GPL-3.0-only
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys

from PySide6.QtCore import QStandardPaths, QTimer, Signal, QObject, Qt
from PySide6.QtNetwork import QNetworkInterface, QAbstractSocket
from PySide6.QtWidgets import (QApplication, QComboBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow,
                               QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from .audio import AudioBridge, list_devices
from .identity import Identity
from .server import RelayServer


class Events(QObject):
    status = Signal(str)


class Window(QMainWindow):
    def __init__(self, identity_directory=None):
        super().__init__()
        self.setWindowTitle('PassThrough')
        self.resize(760, 690)
        self.events = Events()
        self.events.status.connect(self.show_status)
        self.server = None
        self.identity = None
        self.module_ids = []
        self.module_defaults = None
        self.module_name = None
        body = QWidget()
        self.setCentralWidget(body)
        layout = QVBoxLayout(body)
        title = QLabel('PassThrough')
        title.setStyleSheet('font-size: 28px; font-weight: bold')
        layout.addWidget(title)
        caption = QLabel('Computer audio to your hearing aids · hearing-device microphone to your computer')
        caption.setWordWrap(True)
        layout.addWidget(caption)

        connection = QGroupBox('Connection')
        form = QFormLayout(connection)
        self.mode = QComboBox()
        self.mode.addItems(['USB / local connection', 'Wi-Fi / local network', 'Bluetooth · not available yet'])
        form.addRow('Connect by', self.mode)
        self.bind = QLineEdit('127.0.0.1')
        form.addRow('Listen address', self.bind)
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(49721)
        form.addRow('Port', self.port)
        addresses = []
        for interface in QNetworkInterface.allInterfaces():
            for address in interface.addressEntries():
                ip = address.ip()
                if ip.protocol() == QAbstractSocket.IPv4Protocol and not ip.isLoopback():
                    addresses.append(interface.humanReadableName()+': '+ip.toString())
        address_text = QLabel('\n'.join(addresses) or 'No local network address detected')
        address_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow('Computer addresses', address_text)
        self.instructions = QLabel('USB debugging: run adb reverse tcp:49721 tcp:49721, then choose USB debugging in the phone app. USB tethering instead uses the computer’s USB network address.')
        self.instructions.setWordWrap(True)
        form.addRow(self.instructions)
        layout.addWidget(connection)

        pairing = QGroupBox('Verify this computer in the phone app')
        pair_form = QFormLayout(pairing)
        self.fingerprint = QLineEdit()
        self.fingerprint.setReadOnly(True)
        pair_form.addRow('Certificate fingerprint', self.with_copy(self.fingerprint))
        self.token = QLineEdit()
        self.token.setReadOnly(True)
        self.token.setEchoMode(QLineEdit.Password)
        pair_form.addRow('Session token', self.with_copy(self.token))
        layout.addWidget(pairing)

        audio = QGroupBox('Audio routes')
        audio_form = QFormLayout(audio)
        self.capture = QComboBox()
        self.playback = QComboBox()
        audio_form.addRow('Send to phone', self.capture)
        audio_form.addRow('Receive microphone into', self.playback)
        self.refresh = QPushButton('Refresh audio devices')
        self.refresh.clicked.connect(self.refresh_devices)
        audio_form.addRow(self.refresh)
        self.virtual = QPushButton('Create Linux virtual microphone')
        self.virtual.setVisible(sys.platform.startswith('linux'))
        self.virtual.clicked.connect(self.create_virtual_microphone)
        audio_form.addRow(self.virtual)
        note = QLabel('Choose a playback monitor to send computer sound. To use returned audio in a call, choose a virtual-microphone input here and its source in your calling app. Routes are selected explicitly. Silence/Discard tests only the connection.')
        note.setWordWrap(True)
        audio_form.addRow(note)
        layout.addWidget(audio)

        buttons = QHBoxLayout()
        self.start = QPushButton('Start listening')
        self.stop = QPushButton('Stop')
        self.stop.setEnabled(False)
        self.start.clicked.connect(self.start_server)
        self.stop.clicked.connect(self.stop_server)
        buttons.addWidget(self.start)
        buttons.addWidget(self.stop)
        layout.addLayout(buttons)
        self.status = QLabel('Stopped · no audio devices opened')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(QLabel('Development build · Windows 11 and Linux targets · no Windows 10 support'))
        layout.addStretch()
        self.mode.currentIndexChanged.connect(self.mode_changed)
        self.refresh_devices()
        directory = identity_directory or QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
        try:
            self.identity = Identity(Path(directory)/'identity')
            self.fingerprint.setText(self.identity.fingerprint)
            self.token.setText(self.identity.token)
        except Exception as error:
            self.status.setText('Cannot create desktop identity: '+str(error))
            self.start.setEnabled(False)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_server)
        self.timer.start(500)

    def with_copy(self, field):
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(field)
        copy = QPushButton('Copy')
        copy.clicked.connect(lambda: QApplication.clipboard().setText(field.text()))
        row.addWidget(copy)
        return widget

    def mode_changed(self, index):
        self.bind.setText('0.0.0.0' if index == 1 else '127.0.0.1')
        if index == 2:
            self.instructions.setText('Bluetooth computer transport is still being implemented. Wi-Fi and USB are available for testing; this does not enable a native Bluetooth headset role.')
        elif index == 1:
            self.instructions.setText('Use a computer address listed above in the phone app. Listening on 0.0.0.0 allows local-network connections; the phone must verify this certificate and provide the session token. Firewall permission may be needed.')
        else:
            self.instructions.setText('USB debugging: run adb reverse tcp:49721 tcp:49721 for the selected phone. USB tethering uses the computer’s USB network address: set that as the listen address, and enter it on the phone.')
        self.start.setEnabled(index != 2 and self.identity is not None and self.server is None)

    def refresh_devices(self):
        selected_in, selected_out = self.capture.currentData(), self.playback.currentData()
        inputs, outputs = list_devices()
        self.capture.clear()
        self.playback.clear()
        for device in inputs:
            self.capture.addItem(device.name, device.key)
        for device in outputs:
            self.playback.addItem(device.name, device.key)
        self.capture.setCurrentIndex(max(0, self.capture.findData(selected_in)))
        self.playback.setCurrentIndex(max(0, self.playback.findData(selected_out)))

    def start_server(self):
        if self.identity is None or self.server is not None or self.mode.currentIndex() == 2:
            return
        capture, playback = self.capture.currentData(), self.playback.currentData()
        self.server = RelayServer(self.identity, lambda: AudioBridge(capture, playback), self.events.status.emit)
        self.server.start(self.bind.text().strip(), self.port.value())
        for control in (self.start, self.mode, self.bind, self.port, self.capture, self.playback, self.refresh, self.virtual):
            control.setEnabled(False)
        self.stop.setEnabled(True)

    def stop_server(self):
        if self.server is not None:
            self.server.stop()
            self.status.setText('Stopping…')

    def show_status(self, message):
        self.status.setText(message)

    def poll_server(self):
        if self.server is not None and self.server.thread is not None and not self.server.thread.is_alive():
            self.server = None
            for control in (self.mode, self.bind, self.port, self.capture, self.playback, self.refresh, self.virtual):
                control.setEnabled(True)
            self.start.setEnabled(self.identity is not None and self.mode.currentIndex() != 2)
            self.stop.setEnabled(False)

    def create_virtual_microphone(self):
        if self.module_ids:
            self.status.setText('This app already created a virtual microphone. Refresh and select PassThrough Microphone input.')
            return
        if QMessageBox.question(self, 'Create virtual microphone?',
             'Create temporary PipeWire/PulseAudio modules for PassThrough? They will be removed when this app closes. The app preserves existing defaults where possible; desktop audio policy may still move streams. Hearing-aid bonds are unaffected.') != QMessageBox.Yes:
            return
        created = []
        try:
            name = 'passthrough_mic_'+str(os.getpid())
            self.module_defaults = tuple(subprocess.check_output(['pactl','get-default-'+kind],timeout=5).decode().strip() for kind in ('sink','source'))
            self.module_name = name
            commands = [ ['pactl','load-module','module-null-sink','sink_name='+name,
                         'sink_properties=device.description=PassThrough_Microphone_Input'],
                        ['pactl','load-module','module-remap-source','master='+name+'.monitor',
                         'source_name='+name+'_source','source_properties=device.description=PassThrough_Microphone'] ]
            for command in commands:
                result = subprocess.check_output(command, timeout=5, stderr=subprocess.STDOUT).decode().strip()
                if not result.isdigit():
                    raise RuntimeError('Audio service did not return a module ID')
                created.append(result)
            self.module_ids = created
            self.restore_module_defaults()
            self.refresh_devices()
            self.status.setText('Virtual microphone created. Select PassThrough Microphone Input as receive output, then PassThrough Microphone in your calling app.')
        except Exception as error:
            self.restore_module_defaults()
            for module in reversed(created):
                subprocess.run(['pactl','unload-module',module], timeout=5, capture_output=True)
            self.status.setText('Cannot create virtual microphone: '+str(error))

    def restore_module_defaults(self):
        if self.module_defaults is None or self.module_name is None:
            return
        for kind, previous in zip(('sink','source'), self.module_defaults):
            try:
                current=subprocess.check_output(['pactl','get-default-'+kind],timeout=5).decode().strip()
                if current in (self.module_name, self.module_name+'.monitor', self.module_name+'_source'):
                    subprocess.run(['pactl','set-default-'+kind,previous],check=True,timeout=5,capture_output=True)
            except (OSError, subprocess.SubprocessError):
                pass

    def closeEvent(self, event):
        if self.server is not None:
            self.server.stop()
            if not self.server.join(3):
                self.status.setText('Waiting for the relay to stop. Try closing again.')
                event.ignore()
                return
        self.restore_module_defaults()
        for module in reversed(self.module_ids):
            try:
                subprocess.run(['pactl','unload-module',module], timeout=5, capture_output=True)
            except (OSError, subprocess.SubprocessError):
                pass
        event.accept()


def main():
    smoke = '--smoke-test' in sys.argv
    temporary = None
    if smoke:
        import tempfile
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        temporary = tempfile.TemporaryDirectory(prefix='passthrough-smoke-')
    app = QApplication(sys.argv)
    app.setApplicationName('PassThrough')
    app.setOrganizationName('PassThrough')
    window = Window(temporary.name if temporary is not None else None)
    window.show()
    if smoke:
        QTimer.singleShot(100, app.quit)
    result = app.exec()
    if temporary is not None:
        temporary.cleanup()
        print('PassThrough UI smoke test passed; no listener/audio session started')
    return result
