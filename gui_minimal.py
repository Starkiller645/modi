#!/usr/bin/env python3
"""Minimal GUI for the Modi Package installer
Only wraps `install` and `install local`
"""

import modi
import sys
from html.parser import HTMLParser

modi_inst = modi.Modi()

try:
    from PyQt6.QtWidgets import *
    from PyQt6.QtNetwork import *
    from PyQt6.QtCore import *
    from PyQt6.QtGui import *
except ImportError:
    res = modi_inst.try_import('PyQt6')
    try:
        from PyQt6.QtWidgets import *
        from PyQt6.QtNetwork import *
        from PyQt6.QtCore import *
        from PyQt6.QtGui import *
    except ImportError:
        modi_inst.console.log("Could not install PyQt6. Exiting now...", mtype="error")
        sys.exit(1)
modi_inst.try_import("numpy")
import numpy

def fuzzy_search(s, t, ratio_calc=True):
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
    distance = numpy.zeros((rows,cols),dtype = int)

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
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.pkg_name.setWordWrap(True)
        self.setMinimumHeight(60)
        self.spacer.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
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
        self.package_scroll = QScrollArea()
        self.package_frame = QFrame()
        self.queue_widget = QWidget()
        self.queue_layout = QVBoxLayout()
        self.queue_scroll = QScrollArea()
        self.queue_frame = QFrame()
        self.sep = QFrame()
        self.sep.setFrameShape(QFrame.Shape.HLine)
        self.sep.setFrameShadow(QFrame.Shadow.Sunken)
        self.download_bar = QProgressBar()
        self.download_info = QLabel("<i>Downloading package list from PyPi</i>")
        self.install_button = QPushButton("Install")
        self.install_button.setEnabled(False)

        self.add_pkg_shortcut = QShortcut(QKeySequence("Return"), self)
        self.add_pkg_shortcut.setAutoRepeat(False)
        self.add_pkg_shortcut.activated.connect(self.try_add_callback)

        self.install_queue_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.install_queue_shortcut.setAutoRepeat(False)
        self.install_queue_shortcut.activated.connect(self.install_button.click)

        self.pkg_placeholder = QLabel("<i>Search results will appear here</i>")
        self.search_placeholder = QLabel("<i>Add some packages by searching!</i>")

        self.install_button.clicked.connect(self.install)
        
        self.main_widget.setLayout(self.main_layout)
        self.download_info.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.pkg_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.search_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.package_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.queue_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.package_widget.setLayout(self.package_layout)
        self.queue_widget.setLayout(self.queue_layout)
        #self.packages.setWidget(self.package_widget)

        self.package_scroll.setWidgetResizable(True)
        self.queue_scroll.setWidgetResizable(True)

        self.package_scroll.setWidget(self.package_widget)
        self.queue_scroll.setWidget(self.queue_widget)

        self.package_scroll.hide()
        self.package_scroll.setFixedHeight(256)
        self.queue_scroll.hide()
        self.queue_scroll.setFixedHeight(256)

        self.pkg_placeholder.setFixedHeight(256)
        self.search_placeholder.setFixedHeight(256)

        self.main_layout.addWidget(self.input)
        self.main_layout.addWidget(self.download_bar)
        self.main_layout.addWidget(self.download_info)
        self.main_layout.addWidget(self.package_scroll)
        self.main_layout.addWidget(self.pkg_placeholder)
        self.main_layout.addWidget(self.sep)
        self.main_layout.addWidget(self.queue_scroll)
        self.main_layout.addWidget(self.search_placeholder)
        self.main_layout.addWidget(self.install_button)

        self.setCentralWidget(self.main_widget)
        
        self.setFixedSize(645, 630)

        self.to_install = []
        self.pkgs = []
        self.searched_pkgs = []
        self.timers = []

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
        self.queue_scroll.hide()
        self.search_placeholder.show()
        self.pkg_placeholder.show()
        self.install_button.setEnabled(False)


    def update_progress_callback(self, prog):
        try:
            pkg_name = self.queue_layout.itemAt(prog).widget().pkg_name.text()
        except:
            return
        self.download_info.setText(f"<b>Downloading package {pkg_name}</b>")

        if(prog == 0):
            self.download_bar.setRange(0, 0)
        else:
            self.download_bar.setRange(0, len(self.to_install) - 1)
            self.download_bar.setValue(prog)
            self.queue_layout.itemAt(prog - 1).widget().pkg_name.setStyleSheet("color: #5fd7af;")


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
        if error == QNetworkReply.NetworkError.NoError:
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
        if(self.input.text() != ""):
            self.search_pkgs()

    def search_pkgs(self):
        self.searched_pkgs = []
        search = self.input.text()
        for timer in self.timers:
            timer.stop()
            timer.deleteLater()
        if(search == ""):
            self.pkg_placeholder.show()
            self.package_scroll.hide()
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
        else:
            self.searched_pkgs.reverse()
            self.searched_pkgs.sort(key=lambda query, s=search: int(query == s))
            self.searched_pkgs.reverse()
        for i in reversed(range(self.package_layout.count())): 
            self.package_layout.itemAt(i).widget().setParent(None) 

        self.queue_wds = {}
        list_list = []
        if(len(self.searched_pkgs) > 50):
            for i in range(len(self.searched_pkgs) % 50):
                if(i != len(self.searched_pkgs)):
                    list_list.append(self.searched_pkgs[(i * 50):((i + 1) * 50) - 1])
                else:
                    list_list.append(self.searched_pkgs[i * 50:])
            self.timers = []
            for i in range(len(list_list)):
                self.timers.append(QTimer())
                self.timers[i].setSingleShot(True)
                self.timers[i].timeout.connect(lambda a=list_list[i]: self.add_pkg_widgets(a))
                self.timers[i].start(400 * i)
        else:   
                self.timers = []
                self.add_pkg_widgets(self.searched_pkgs)

        
    def add_pkg_widgets(self, arr):
        for pkg in arr:
            self.queue_wds[pkg] = Package(pkg, "v0.1")
            if(pkg == self.input.text()):
                self.queue_wds[pkg].pkg_name.setStyleSheet("color: #afd7ff;")
            self.queue_wds[pkg].add.clicked.connect(lambda nul, pkg=pkg: self.add_pkg(pkg))
            self.package_layout.addWidget(self.queue_wds[pkg])
        if(len(self.queue_wds) != 0):
            self.pkg_placeholder.hide()
            self.package_scroll.show()
        if(len(self.queue_wds) == 0):
            self.package_scroll.hide()
            self.pkg_placeholder.show()



    def try_add_callback(self):
        search = self.input.text()
        if(search in self.queue_wds.keys()):
            self.add_pkg(search)
        else:
            return

    def add_pkg(self, pkg):
        for i in reversed(range(self.package_layout.count())): 
            self.package_layout.itemAt(i).widget().setParent(None) 
        self.queue_wds[pkg].setParent(None)
        self.queue_wds[pkg].queue()
        self.queue_layout.addWidget(self.queue_wds[pkg])
        self.input.setText("")
        self.to_install.append(pkg)
        print(self.package_scroll.size())
        print(self.queue_scroll.size())
        if(len(self.queue_wds) > 0):
            self.search_placeholder.hide()
            self.queue_scroll.show()
            self.install_button.setEnabled(True)
        if(len(self.queue_wds) == 0):
            self.queue_scroll.hide()
            self.search_placeholder.show()

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = ModiMinimalWindow()
    window.show()
    app.exec()
