#!/usr/bin/env python3

import modi

try:
    from PySide2.QtWidgets import *
except ImportError:
    import importlib
    modi_inst = modi.Modi()
    modi_inst.install_local(["PySide2"])
    from PySide2.QtWidgets import *

if(__name__ == "__main__"):
    app = QApplication([])
    window = QWidget()
    layout = QVBoxLayout()
    window.setLayout(layout)
    label = QLabel("Hello from PySide2 and Modi!")
    layout.addWidget(label)
    window.show()
    app.exec_()
