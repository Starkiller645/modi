#!/usr/bin/env python3
"""Minimal GUI for the Modi Package installer
Only wraps `install` and `install local`
"""

import modi
import sys
from html.parser import HTMLParser

modi_inst = modi.Modi()

try:
    from PyQt5.QtWidgets import *
    from PyQt5.QtNetwork import *
    from PyQt5.QtCore import *
except ImportError:
    if not modi_inst.console.prompt_bool("Modi GUI requires PyQt5. Install?"):
        sys.exit(1)
    if modi_inst.install_local(["PyQt5"]) == 1:
        modi_inst.console.log("Could not install PyQt5. Exiting now...", mtype="error")
        sys.exit(1)
    try:
        from PyQt5.QtWidgets import *
        from PyQt5.QtNetwork import *
        from PyQt5.QtCore import *
    except ImportError:
        modi_inst.console.log("Could not install PyQt5. Exiting now...", mtype="error")
        sys.exit(1)

def fuzzy_search(s, t, ratio_calc=True):
    import numpy as np
    """ levenshtein_ratio_and_distance:
        Calculates levenshtein distance between two strings.
        If ratio_calc = True, the function computes the
        levenshtein distance ratio of similarity between two strings
        For all i and j, distance[i,j] will contain the Levenshtein
        distance between the first i characters of s and the
        first j characters of t
    """
    rows = len(s)+1
    cols = len(t)+1
    distance = np.zeros((rows,cols),dtype = int)

    for i in range(1, rows):
        for k in range(1,cols):
            distance[i][0] = i
            distance[0][k] = k

    for col in range(1, cols):
        for row in range(1, rows):
            if s[row-1] == t[col-1]:
                cost = 0 
            else:
                if ratio_calc == True:
                    cost = 2
                else:
                    cost = 1
            distance[row][col] = min(distance[row-1][col] + 1,      # Cost of deletions
                                 distance[row][col-1] + 1,          # Cost of insertions
                                 distance[row-1][col-1] + cost)     # Cost of substitutions
    if ratio_calc == True:
        Ratio = ((len(s)+len(t)) - distance[row][col]) / (len(s)+len(t))
        return Ratio
    else:
        return "The strings are {} edits away".format(distance[row][col])

class Package(QWidget):
    def __init__(self, package_name, package_ver, active=False):
        super().__init__()
        self.main_layout = QHBoxLayout()
        self.pkg_name = QLabel(f"<h1>{package_name}</h1>")
        self.pkg_ver = QLabel(f"<i>{package_ver}</i>")
        self.add = QPushButton("Add")
        self.spacer = QWidget()
        self.spacer.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        self.main_layout.addWidget(self.pkg_name)
        self.main_layout.addWidget(self.pkg_ver)
        self.main_layout.addWidget(self.spacer)
        self.main_layout.addWidget(self.add)
        self.setLayout(self.main_layout)

    def queue(self):
        self.pkg_name.setStyleSheet("font-weight: bold; color: #ffafaf;")
        self.add.hide()

class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

class MLWorker(QObject):

    finished = pyqtSignal(list)

    def __init__(self, bytes_str):
        self.bytes_str = bytes_str
        super().__init__()
    def run(self):  
        pkg_html = str(self.bytes_str, 'utf-8')
        stripper = MLStripper()
        stripper.feed(pkg_html)
        data = stripper.get_data()
        data_list = data.split("\n")
        for line in data_list:
            line = line.strip()
        self.finished.emit(data_list)

class ModiInstallWorker(QObject):
    finished = pyqtSignal(int)
    progress = pyqtSignal(int)

    def __init__(self, pkgs):
        self.packages = pkgs
        super().__init__()

    def run(self):
        import os
        import subprocess
        modi_inst = modi.Modi()
        self.progress.emit(0)
        i = 1
        print("installing packages")
        for pkg in self.packages:
            print(pkg)
            print("Installing package " + pkg)
            pkg_arr = []
            pkg_arr.append(pkg)
            modi_inst.install_local(pkg_arr, no_projects=False, add_reqs=False)
            self.progress.emit(i)
            i += 1
        self.finished.emit(0)

class ModiMinimalWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modi GUI - Python Package Installer")
        self.modi = modi.Modi()
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Search for packages...")
        #self.packages = QScrollArea()
        self.package_widget = QWidget()
        self.package_layout = QVBoxLayout()
        self.queue_widget = QWidget()
        self.queue_layout = QVBoxLayout()
        self.sep = QFrame()
        self.sep.setFrameShape(QFrame.HLine)
        self.sep.setFrameShadow(QFrame.Sunken)
        self.download_bar = QProgressBar()
        self.download_info = QLabel("<i>Downloading package list from PyPi</i>")
        self.install_button = QPushButton("Install")
        self.install_button.setStyleSheet("color: #ffafaf; font-weight: bold; font-size: 14px;")
        self.install_button.setEnabled(False)

        self.pkg_placeholder = QLabel("<i>Search results will appear here</i>")
        self.search_placeholder = QLabel("<i>Add some packages by searching!</i>")

        self.install_button.clicked.connect(self.install)
        
        self.main_widget.setLayout(self.main_layout)
        self.download_info.setAlignment(Qt.AlignTop)
        self.pkg_placeholder.setAlignment(Qt.AlignCenter)
        self.search_placeholder.setAlignment(Qt.AlignCenter)
        self.package_widget.setLayout(self.package_layout)
        self.queue_widget.setLayout(self.queue_layout)
        #self.packages.setWidget(self.package_widget)

        self.package_widget.hide()
        self.queue_widget.hide()

        self.main_layout.addWidget(self.input)
        self.main_layout.addWidget(self.download_bar)
        self.main_layout.addWidget(self.download_info)
        self.main_layout.addWidget(self.package_widget)
        self.main_layout.addWidget(self.pkg_placeholder)
        self.main_layout.addWidget(self.sep)
        self.main_layout.addWidget(self.queue_widget)
        self.main_layout.addWidget(self.search_placeholder)
        self.main_layout.addWidget(self.install_button)

        self.setCentralWidget(self.main_widget)
        
        self.setFixedSize(645, 630)

        self.to_install = []
        self.pkgs = []
        self.searched_pkgs = []
        self.download_pypi_index()

    def install(self):
        self.input.hide()
        #self.package_widget.hide()
        self.pkg_placeholder.hide()
        self.download_info.setText("<b>Installing packages...</b>")
        self.download_info.show()
        self.download_bar.setRange(0, len(self.to_install))
        self.download_bar.show()

        self.worker_2 = ModiInstallWorker(self.to_install)
        self.thread_2 = QThread()
        self.worker_2.moveToThread(self.thread_2)
        
        self.thread_2.started.connect(self.worker_2.run)
        self.worker_2.finished.connect(self.install_callback)
        self.worker_2.progress.connect(self.update_progress_callback)
        self.worker_2.finished.connect(self.worker_2.deleteLater)
        self.thread_2.finished.connect(self.thread_2.deleteLater)

        self.thread_2.start()

    def install_callback(self, status):
        if(status == 1):
            self.download_info.setText("<i>Package download failed</i>")
            self.download_info.show()
        else:
            self.download_info.hide()
            self.download_bar.hide()
            self.input.show()
            self.sep.show()
        for i in reversed(range(self.queue_layout.count())): 
            self.queue_layout.itemAt(i).widget().setParent(None) 
        self.queue_widget.hide()
        self.search_placeholder.show()
        self.pkg_placeholder.show()


    def update_progress_callback(self, prog):
        if(prog == 0):
            self.download_bar.setRange(0, 0)
        else:
            self.download_bar.setRange(0, len(self.to_install))
            self.download_bar.setValue(prog)

    def download_pypi_index(self):
        url = "https://pypi.org/simple/"
        req = QNetworkRequest(QUrl(url))

        self.net_man = QNetworkAccessManager()
        self.net_man.finished.connect(self.download_finished)
        
        res = self.net_man.get(req)
        res.downloadProgress.connect(self.download_progress)

    def download_progress(self, current, maxi):
        self.download_bar.setRange(0, maxi * 2)
        self.download_bar.setValue(current)
        
    def download_finished(self, res):
        error = res.error()
        self.download_bar.setRange(0, 100)
        self.download_bar.setValue(50)
        self.download_info.setText("<i>Formatting package list...</i>")
        if error == QNetworkReply.NoError:
            bytes_str = res.readAll()
            self.thread = QThread()
            self.ml_worker = MLWorker(bytes_str)
            self.ml_worker.moveToThread(self.thread)
            self.thread.started.connect(self.ml_worker.run)
            self.ml_worker.finished.connect(self.update_pkg_callback)
            self.ml_worker.finished.connect(self.ml_worker.deleteLater)
            self.thread.finished.connect(self.thread.deleteLater)
            self.thread.start()
        else:
            self.main_layout.addWidget(QLabel(f"Error: {res.errorString()}"))
    
    def update_pkg_callback(self, pkgs):
        self.pkgs = pkgs
        self.download_bar.hide()
        self.download_info.hide()
        for i in range(len(self.pkgs) - 1):
            self.pkgs[i] = self.pkgs[i].strip()
        self.download_bar.setValue(100)
        self.input.textChanged.connect(self.search_pkgs)

    def search_pkgs(self):
        self.searched_pkgs = []
        search = self.input.text()
        if(search == ""):
            self.pkg_placeholder.show()
            self.package_widget.hide()
            return
        if(len(search) >= 4):
            for pkg in self.pkgs:
                if(search in pkg):
                    self.searched_pkgs.append(pkg)
        else:
            for pkg in self.pkgs:
                if(search == pkg):
                    self.searched_pkgs.append(pkg)

        if(len(search) >= 4 and len(self.searched_pkgs) <= 300):
            self.searched_pkgs.sort(key=lambda query, s=search: fuzzy_search(query, s))
            self.searched_pkgs.reverse()
        for i in reversed(range(self.package_layout.count())): 
            self.package_layout.itemAt(i).widget().setParent(None) 

        self.queue_wds = {}
        
        for pkg in self.searched_pkgs[:5]:
            self.queue_wds[pkg] = Package(pkg, "v0.1")
            self.queue_wds[pkg].add.clicked.connect(lambda nul, pkg=pkg: self.add_pkg(pkg))
            self.package_layout.addWidget(self.queue_wds[pkg])


        if(len(self.queue_wds) != 0):
            self.pkg_placeholder.hide()
            self.package_widget.show()
        if(len(self.queue_wds) == 0):
            self.package_widget.hide()
            self.pkg_placeholder.show()

    def add_pkg(self, pkg):
        for i in reversed(range(self.package_layout.count())): 
            self.package_layout.itemAt(i).widget().setParent(None) 
        self.queue_wds[pkg].setParent(None)
        self.queue_wds[pkg].queue()
        self.queue_layout.addWidget(self.queue_wds[pkg])
        self.input.setText("")
        self.to_install.append(pkg)
        if(len(self.queue_wds) > 0):
            self.search_placeholder.hide()
            self.queue_widget.show()
            self.install_button.setEnabled(True)
        if(len(self.queue_wds) == 0):
            self.queue_widget.hide()
            self.search_placeholder.show()

if __name__ == "__main__":
    app = QApplication([])
    window = ModiMinimalWindow()    
    window.show()
    app.exec_()

