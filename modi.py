#!/usr/bin/env python3

import json
import os
import sys
import urllib.request
import subprocess
import tarfile
import re
import shutil
import time
termtype = "plain"
try:
    import rich
    import rich.progress
    termtype = "rich"
except ImportError:
    termtype = "plain"

class Output:
    def __init__(self, termtype):
        if(termtype == "rich"):
            self.termtype = "rich"
        else:
            self.termtype = 'plain'

    def log(self, text, mtype="message"):
        style = "bold"
        padding = ""
        if(mtype == "error"):
            style = "bold red"
            padding += " " * 5
        elif(mtype == "info"):
            style = "bold cyan"
            padding += " " * 6
        elif(mtype == "message"):
            style = "bold green"
            padding += " " * 3
        elif(mtype == "warning"):
            style = "bold yellow"
            padding += " " * 3
        elif(mtype == "completion"):
            style = "bold bright_blue"
        if self.termtype == 'plain':
            print(f"[MODI] ({mtype}) {padding} {text} ")
        else:
            rich.print(f"    [[{style}]MODI[/{style}]] ([{style}]{mtype}[/{style}]) {padding} {text}  ")

    def clear(self): 
        if(os.name != "posix"):
            os.system('cls')
        else:
            os.system('clear')

class Modi:
    def __init__(self, *args):
        self.env_home = os.getenv("HOME", "")
        global termtype
        self.console = Output(termtype)
        try:
            with open(f"{self.env_home}/.modi.json", "r") as conf:
                self.config = json.loads(conf.read())
        except:
            self.console.log("Config file not found, bootstrapping...", mtype="warning")
            with open(f"{self.env_home}/.modi.json", "w") as conf:
                filepath = f"{self.env_home}/.modi_cache/"
                os.mkdir(f"{self.env_home}/.modi_cache/")
                json_conf = {"cache": {"path": filepath}}
                conf.write(json.dumps(json_conf))
            with open(f"{self.env_home}/.modi.json", "r") as conf:
                self.config = json.loads(conf.read())
        self.console.log("Starting MODI v0.1")
        self.parseargs(args[0])

    def help(self, name=""):
        self.console.log("MODI Help:", mtype="info")
        if name not in ["install", "help"]:
            self.console.log("- modi.py install [args] : Installs one or more packages", mtype="info")
            self.console.log("- modi.py help [cmd]     : Shows the help page, either this or the detailed view for [cmd]", mtype="info")
        elif name == "install":
            self.console.log("- modi.py install <package> [package] [...]         : Installs one or more packages to the global MODI cache (by default @ ~/.modi_cache)", mtype="info")
            self.console.log("  > modi.py install @<package> [package] [...]      : Same as above, but forcing use of the setuptools install method. Use if the previous option isn't working.", mtype="info")
            self.console.log("- modi.py install local <package> [package] [...]   : Installs one or more packages to the current working directory. This means they can be directly imported using `import <package>`", mtype="info")
            self.console.log("  > modi.py install local @<package> [package] [...]: Same as above, but forcing use of the setuptools install method. Use if the previous option isn't working.", mtype="info")
        elif name == "remove":
            self.console.log("- modi.py remove <package> [package] [...]        : Removes one or more packages from the global MODI cache.", mtype="info")
            self.console.log("  > modi.py remove local <package> [package] [...]: Removes one or more packages from the current working directory.", mtype="info")
        elif name == "help":
            self.console.log("- modi.py help        : Shows the short help view for MODI.", mtype="info")
            self.console.log("  > modi.py help [cmd]: Shows detailed help for a specific command.", mtype="info")


    def parseargs(self, *args):
        args = args[0]
        if(len(args) <= 0):
            self.console.log("Error: no valid operation specified", mtype="error")
            return 1
        if(args[0] == "install"):
            if(len(args) > 1):
                self.install(args[1:])
            else:
                self.console.log("Error: not enough arguments passed to command `install`", mtype="error")
                return 1
        elif(args[0] == "help"):
            if(len(args) <= 1):
                self.help()
            else:
                self.help(name=args[1])
        elif(args[0] == "remove"):
            self.remove(args[1:])
        else:
            self.console.log("Error: no valid operation specified", mtype="error")
            return 1

    def install(self, *args):
        print(args)
        args = args[0]
        local = False
        cwd = ""
        packages = []
        if args[0] == "local":
            local = True
            cwd = os.getcwd()
            if(len(args) > 1):
                packages = args[1:]
            else:
                return 1
        else:
            cwd = self.config["cache"]["path"]
            packages = args
        self.prefix = cwd

        setup_py_queue = []
        pkg_count = len(packages)
        start_time = time.perf_counter()
        global termtype
        if(termtype == "rich"):
            for pkg in rich.progress.track(packages, description="    Installing..."):
                mode = "PIP"
                if(pkg[0] == "@"):
                    mode = "SETUPTOOLS"
                    pkg = pkg[1:]
                self.console.log(f"Installing package {pkg}", mtype="message")
                if(mode == "PIP"):
                    res = self.install_pip(pkg)
                    if(res == 1):
                        setup_py_queue.append(pkg)
                    else:
                        continue
                else:
                    res = self.install_setuptools(pkg)
                    if(res == 1):
                        self.console.log("Error: failed to install package " + pkg, mtype="error")
                    else:
                        self.console.log(f"Installed package {pkg}", mtype="message")

        for pkg in packages:
            mode = "PIP"
            if(pkg[0] == "@"):
                mode = "SETUPTOOLS"
                pkg = pkg[1:]
            self.console.log(f"Installing package {pkg}", mtype="message")
            if(mode == "PIP"):
                res = self.install_pip(pkg)
                if(res == 1):
                    setup_py_queue.append(pkg)
            else:
                res = self.install_setuptools(pkg)
                if(res == 1):
                    self.console.log("Error: failed to install package " + pkg, mtype="error")
                else:
                    self.console.log(f"Installed package {pkg}", mtype="message")
        if(local):
            self.console.log("Local mode selected, copying files to CWD", mtype="message")
            for file in os.listdir("./lib/python3.10/site-packages"):
                suffix = ""
                try:
                    suffix = file.split("1", 1)[1]
                except:
                    suffix = ""
                if (file in packages or file.split("-")[0] in packages) and "info" not in suffix:
                    try:
                        shutil.copytree(f"./lib/python3.10/site-packages/{file}", f"./{file}")
                    except FileExistsError:
                        pass
        finish_time = time.perf_counter()
        total_time = str(round(finish_time - start_time, 2))
        pkg_count = str(pkg_count)
        keyword = "to Modi cache"
        if(local):
            keyword = f"locally, to {self.prefix}"
        self.console.log(f"Installed {pkg_count} packages {keyword} in {total_time} seconds", mtype="completion") 

    def install_pip(self, pkg):
        current_env = os.environ.copy()
        current_env["PYTHONPATH"] = self.prefix + "/lib/site-packages/"
        inst_result = subprocess.run(f"{sys.executable} -m pip install --quiet --ignore-installed --no-warn-script-location {pkg} --prefix {self.prefix}", env=current_env, shell=True)
        if(inst_result.returncode != 0):
            self.console.log(f"Installing package {pkg} failed, adding to setuptools queue", mtype="warning")
            return 1
        else:
            self.console.log(f"Installed package {pkg}", mtype="completion")
            return 0

    def install_setuptools(self, pkg):
        pkg_json_data = ""
        with urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json") as res:
            pkg_json_data = res.read().decode("UTF-8")
        pkg_json_obj = json.loads(pkg_json_data)
        package_url = ""
        for url in pkg_json_obj["urls"]:
            if url["packagetype"] == "sdist" and url["python_version"] == "source":
                package_url = url["url"]
        pkg_version = pkg_json_obj["info"]["version"]

        with urllib.request.urlopen(package_url) as package_req:
            with open(f"{pkg}-{pkg_version}.tar.gz", "wb") as tarf:
                tarf.write(package_req.read())
        
        tarball = tarfile.open(f"{pkg}-{pkg_version}.tar.gz", mode='r:gz')
        tarball.extractall(f".")
        os.remove(f"{pkg}-{pkg_version}.tar.gz")
        current_env = os.environ.copy()
        current_env["PYTHONPATH"] = self.prefix + "/lib/python3.10/site-packages/"
        cwd = os.getcwd()
        os.chdir(f"./{pkg}-{pkg_version}")
        inst_result = subprocess.run(f"{sys.executable} ./setup.py --quiet install --prefix {self.prefix}", env=current_env, shell=True)
        os.chdir(cwd)
        shutil.rmtree(f"./{pkg}-{pkg_version}")
        try:
            shutil.rmtree(f"{pkg}.egg-info")
        except:
            pass
        if(inst_result.returncode == 0):
            return 0
        else:
            return 1
    
    def remove(self, *args):
        local = False
        packages = []
        args = args[0]
        self.console.log("Removing packages", mtype="warning")
        start_time = time.perf_counter()
        if(args[0] == "local"):
            packages = args[1:]
            local = True
            self.prefix = os.getcwd()
        else:
            packages = args
            self.prefix = self.config["cache"]["path"]
        pkg_count = len(packages)
        for pkg in packages:
            for fd in os.listdir(f"{self.prefix}/lib/python3.10/site-packages/"):
                if pkg in fd:
                    shutil.rmtree(f"{self.prefix}/lib/python3.10/site-packages/{fd}")
            if(local):
                for fd in os.listdir(f"{self.prefix}/"):
                    if pkg in fd:
                        shutil.rmtree(f"{self.prefix}/{fd}")
        end_time = time.perf_counter()
        total_time = str(round(end_time - start_time, 2))
        self.console.log(f"Removed {str(pkg_count)} packages in {total_time} seconds", mtype="completion")

if __name__ == "__main__":
    modi_instance = Modi(sys.argv[1:])
