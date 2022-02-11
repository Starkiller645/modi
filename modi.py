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
from pathlib import Path
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

    def prompt_bool(self, text, mtype="warning"):
        if self.termtype == "plain":
            choices = ["y", "n", ""]
            choice = " "
            while choice.lower() not in choices:
                choice = input(f"{text}\n[Y]es or [n]o >> ")
            if(choice.lower() == "y" or choice.lower == ""):
                return True
            else:
                return False
        else:
            from rich.prompt import Confirm
            return_value = Confirm.ask(f"{text}")
            return return_value


    def clear(self): 
        if(os.name != "posix"):
            os.system('cls')
        else:
            os.system('clear')

class Modi:
    def __init__(self, args, mode="module"):
        self.env_home = os.getenv("HOME", "")
        global termtype
        self.console = Output(termtype)
        self.termtype = termtype
        try:
            with open(f"{self.env_home}/.modi.json", "r") as conf:
                self.config = json.loads(conf.read())
        except:
            self.console.log("Config file not found, bootstrapping...", mtype="warning")
            with open(Path(f"{self.env_home}/.modi.json", "w")) as conf:
                filepath = Path(f"{self.env_home}/.modi_cache/")
                os.mkdir(Path(f"{self.env_home}/.modi_cache/"))
                json_conf = {"cache": {"path": filepath}}
                conf.write(json.dumps(json_conf))
            with open(Path(f"{self.env_home}/.modi.json", "r")) as conf:
                self.config = json.loads(conf.read())
        self.site_prefix = ""    
        if(os.name != "unix"):
            self.windows = True
            self.site_prefix = "/lib/site-packages/"
        else:
            self.windows = False
            self.site_prefix = f"/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages/"

        if(mode == "module"):
           pass 
        elif(mode == "interactive"): 
            self.console.log("Starting MODI v0.2")
            self.parseargs(args)

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
    
    def copy_local(self, path, dest):
        dest_files = os.listdir(dest)
        loop_var = []
               
        if(self.termtype == "rich"):
            loop_var = rich.progress.track(os.listdir(path), description="    Installing...", transient=True)
        else:
            loop_var = os.listdir(path)
        for fd in loop_var:
            pkg_type = "dependency"
            if "info" not in fd and "egg" not in fd:
                if(fd in self.packages):
                    pkg_type = "package"
                if(fd not in dest_files):
                    self.console.log(f"Installing {pkg_type} '{fd}'")
                try:
                    shutil.copytree(Path(f"{path}/{fd}"), f"{dest}/{fd}")
                except NotADirectoryError:
                    try:
                        shutil.copy(Path(f"{path}/{fd}"), f"{dest}/{fd}")
                    except FileExistsError:
                        pass
                except FileExistsError:
                    pass
            elif "egg" in fd and "info" not in fd:
                copy_list = []
                for file in os.listdir(Path(f"{path}/{fd}")):
                    if file != "EGG-INFO":
                        copy_list.append(file)
                for file in copy_list:
                    if(file not in dest_files):
                        if(file in self.packages):
                            pkg_type = "package"
                        self.console.log(f"Installing {pkg_type} '{file}'")
                    try:
                        shutil.copytree(Path(f"{path}/{fd}/{file}"), "{dest}/{file}")
                    except NotADirectoryError:
                        try:
                            shutil.copy(Path(f"{path}/{fd}/{file}"), "{dest}/{file}")
                        except FileExistsError:
                            pass
                    except FileExistsError:
                        pass
            else:
                pass
    def install_local(self, *args):
        packages = []
        for arg in args:
            packages.append(arg[0])
        
        inst_args = ["local"]
        for pkg in packages:
            inst_args.append(pkg)
        self.console.log(inst_args)
        self.install(inst_args)

    def install(self, *args):
        self.tracked_pkgs = 0
        self.packages = []
        if(len(args) == 0):
            return 1
        elif(isinstance(args, str)):
            args = list(args)
        elif(isinstance(args, tuple)):
            args = args[0]
        else:
            pass
        local = False
        cwd = ""
        self.packages = []
        if args[0] == "local":
            local = True
            cwd = str(Path(os.getcwd()))
            if(len(args) > 1):
                self.packages = args[1:]
            else:
                return 1
        else:
            cwd = str(Path(self.config["cache"]["path"]))
            self.packages = args
        self.prefix = cwd

        setup_py_queue = []
        pkg_count = len(self.packages)
        total_deps = 0
        start_time = time.perf_counter()

        global termtype
        if(termtype == "rich"):
            count = 0
            for pkg in rich.progress.track(self.packages, description="    Downloading & Building...", transient=True):

                dep_count = 0
                mode = "PIP"
                verb = "Installing"
                if(local):
                    verb = "Downloading"
                if(pkg[0] == "@"):
                    mode = "SETUPTOOLS"
                    pkg = pkg[1:]

                if(mode == "PIP"):
                    self.console.log(f"{verb} package '{pkg}' with PIP", mtype="message")
                    res = self.install_pip(pkg)
                    count += 1
                    dep_count = len(os.listdir(Path(f"{self.prefix}/{self.site_prefix}"))) - count - total_deps
                    total_deps += dep_count
                    if(res == 1):
                        print("Done")
                        if(self.prefix == str(Path(os.getcwd()))):
                            self.console.log(f"Downloaded package '{pkg}' and {str(dep_count)} dependencies", mtype="completion")    
                        else:
                            self.console.log(f"Installed package '{pkg}' and {str(dep_count)} dependencies", mtype="completion")
                        setup_py_queue.append(pkg)

                else:
                    self.console.log(f"{verb} package '{pkg}' with setuptools", mtype="message")
                    res = self.install_setuptools(pkg)
                    if(res == 1):
                        self.console.log("Error: failed to install package " + pkg, mtype="error")
                    else:
                        if(local):
                            self.console.log(f"Downloaded and built package '{pkg}'", mtype="message")
                        else:
                            self.console.log(f"Installed package '{pkg}'", mtype="message")

        else:
            for pkg in self.packages:
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
            self.copy_local(str(Path(f"{os.getcwd()}/{self.site_prefix}")), "./")
            shutil.rmtree(Path("./lib"))
            try:
                shutil.rmtree(Path("./scripts"))
            except:
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
        current_env["PYTHONPATH"] = str(Path(self.prefix) / Path(self.site_prefix))
        if(os.name != "unix"):
            inst_result = subprocess.run(f"py -m pip install --disable-pip-version-check --quiet --ignore-installed --no-warn-script-location {pkg} --prefix \"{self.prefix}\"", env=current_env, shell=True)
        else:
            inst_result = subprocess.run(f"'{sys.executable}' -m pip install --quiet --ignore-installed --no-warn-script-location {pkg} --prefix {self.prefix}", env=current_env, shell=True)
        if(inst_result.returncode != 0):
            self.console.log(f"Installing package {pkg} failed, adding to setuptools queue", mtype="warning")
            return 1
        else:

            return 0

    def install_setuptools(self, pkg):
        if(not os.path.exists(Path(f"{self.prefix}{self.site_prefix}"))):
            path = Path(f"{self.prefix}{self.site_prefix}")
            path.mkdir(parents=True)
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
        self.console.log("Downloaded release tarball")
        tarball = tarfile.open(f"{pkg}-{pkg_version}.tar.gz", mode='r:gz')
        tarball.extractall(f".")
        tarball.close()
        os.remove(f"{pkg}-{pkg_version}.tar.gz")
        self.console.log("Extracted")
        current_env = os.environ.copy()
        current_env["PYTHONPATH"] = str(Path(self.prefix) / Path(self.site_prefix))
        cwd = os.getcwd()
        os.chdir(Path(f"./{pkg}-{pkg_version}"))
        if(self.windows):
            inst_result = subprocess.run(f"py ./setup.py --quiet install --prefix \"{self.prefix}\"", env=current_env, shell=True)
        else:
            inst_result = subprocess.run(f"{sys.executable} ./setup.py --quiet install --prefix {self.prefix}", env=current_env, shell=True)
        self.console.log("Finished running setup.py install", mtype="completion")
        os.chdir(cwd)
        shutil.rmtree(Path(f"./{pkg}-{pkg_version}"))
        try:
            shutil.rmtree(Path(f"./{pkg}.egg-info"))
        except:
            pass
        if(inst_result.returncode == 0):
            return 0
        else:
            return 1
    
    def remove(self, *args):
        local = False
        self.packages = []
        args = args[0]
        self.console.log("Removing packages", mtype="warning")
        start_time = time.perf_counter()
        if(args[0] == "local"):
            if(len(args) >= 2):
                if(args[1] == "all"):
                    if not self.console.prompt_bool("Warning: this is a potentially destructive action.\nRunning `remove local all` will delete all subdirs in this project. Continue?"):
                            return 1
                    for filename in os.listdir(Path("./")):
                        if "." in filename:
                            if(filename.split(".")[len(filename.split(".")) - 1] != "py" and "modi" not in filename):
                                try:
                                    os.remove(Path(f"./{filename}"))
                                except PermissionError:
                                    pass
                        else:
                            try:
                                shutil.rmtree(Path(f"./{filename}"))
                            except:
                                pass
                    return 0
            self.packages = args[1:]
            local = True
            self.prefix = os.getcwd()
        else:
            self.packages = args
            self.prefix = self.config["cache"]["path"]
        pkg_count = len(self.packages)
        for pkg in self.packages:
            for fd in os.listdir(Path(f"{self.prefix}")):
                if pkg in fd:
                    shutil.rmtree(Path(f"{self.prefix}/{fd}"))
            if(local):
                for fd in os.listdir(Path(f"{self.prefix}/")):
                    if pkg in fd:
                        shutil.rmtree(Path(f"{self.prefix}/{fd}"))
        end_time = time.perf_counter()
        total_time = str(round(end_time - start_time, 2))
        self.console.log(f"Removed {str(pkg_count)} packages in {total_time} seconds", mtype="completion")

if __name__ == "__main__":
    modi_instance = Modi(sys.argv[1:], mode="interactive")
