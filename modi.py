#!/usr/bin/env python3
"""A local package installer for python3 (and output helper class).

Modi is a local package installer that can install PyPi and setuptools packages to
either a global cache or directly into the CWD, for easy import and packaging. It can
also build egg files and sdists that it can install at a later date, using modi.py build

Typical usage example:

    import modi
    modi_instance = modi.Modi()
    modi_instance.install(["asciimatics"]) # installs to global cache
    modi_instance.install(["rich", "PyQt5", "colorama"]) # installs multiple pkgs to CWD
    modi_instance.build("freeze") # builds a zip-file from installed packages and python files

:x-modi-build-requires:
"""

import json
import os
import sys
import urllib.request
import subprocess
import tarfile
import re
import shutil
import time
import requests
from pathlib import Path
from io import StringIO
import glob
import readline
termtype = "plain"
modi_version = "v0.7.4"
try:
    import rich
    import rich.progress
    termtype = "rich"
except ImportError:
    termtype = "plain"

def check_IDLE():
    return("idlelib" in sys.modules)

if check_IDLE():
    termtype = "plain"

class Output:
    def __init__(self, termtype, loudness):
        if(termtype == "rich"):
            self.termtype = "rich"
        else:
            self.termtype = 'plain'
        self.loudness = loudness
        self.project = ""

    def set_loudness(self, loudness):
        self.loudness = loudness

    def log(self, text, mtype="message"):
        if(self.loudness == "off"):
            return
        style = "bold"
        padding = ""
        if(mtype == "error"):
            style = "bold red"
            padding += " " * 5
        elif(mtype == "warning"):
            style = "bold yellow"
            padding += " " * 3
        elif(mtype == "info"):
            style = "bold cyan"
            padding += " " * 6
        elif(mtype == "message"):
            style = "bold green"
            padding += " " * 3
        elif(mtype == "completion"):
            style = "bold bright_blue"
        if self.termtype == 'plain':
            if((self.loudness == "quiet" and mtype not in ["message", "info", "completion"]) or self.loudness == "norm" and self.loudness != "off"):
                print(f"    [MODI] ({mtype}) {padding} {text} ")
        else:
            if((self.loudness == "quiet" and mtype not in ["message", "info", "completion"]) or self.loudness == "norm" and self.loudness != "off"):
                rich.print(f"    [[bold]MODI[/bold]] ([{style}]{mtype}[/{style}]) {padding} {text}  ")

    def prompt_bool(self, text, mtype="warning"):
        if self.termtype == "plain":
            choices = ["y", "n", ""]
            choice = " "
            while choice.lower() not in choices:
                choice = input(f"{text}\n    [Y]es or [n]o >> ")
            if(choice.lower() == "y" or choice.lower == ""):
                return True
            else:
                return False
        else:
            from rich.prompt import Confirm
            return_value = Confirm.ask(f"{text}")
            return return_value
    
    def prompt_selection(self, text, choices):
        if(self.termtype == "plain"):
            choice_valid = False
            print(text)
            i = 1
            for choice in choices:
                print(f"{i}.   {choice}")
                i += 1
            choice = 0
            while(not choice_valid):
                choice = input(f"    Please select an option [1-{i}]\n    >>")
                if(choice < 1 or choice > i):
                    continue
                try:
                    choice = int(choice)
                    choice_valid = True
                except:
                    continue
            return choice
        else:
            from rich.prompt import IntPrompt
            i = 1
            for choice in choices:
                rich.print(f"    [{i}.] [bold orchid1]{choice}[/bold orchid1]")
                i += 1
            return_value = IntPrompt(choices=choices).ask(text)
            return return_value

    
    def prompt(self, text, choices=[], password=False):
        choice = ""
        if(self.termtype == "plain"):
            if(len(choices) != 0):
                while choice not in choices:
                    choice = input(f"{text}\n    Enter a choice from {choices}\n    >> ")
            else:
                choice = input(f"    {text}\n    >> ")
            return choice
        else: 
            from rich.prompt import Prompt
            if(len(choices) == 0):
                choice = Prompt.ask(f"    {text}", password=password)
            else:
                choice = Prompt.ask(f"    {text}", choices=choices, password=password)
            return choice

    def shell_prompt(self):
        if(self.termtype == "plain"):
            if(self.project == ""):
                return input("    [MODI shell] > ").split(" ")
            else:
                return input(f"    [MODI shell in '{self.project}'] > ").split(" ")
        else:
            from rich.prompt import Prompt
            prompt_string = ""
            if(self.project == ""):
                prompt_string = f"    [[bold][sky_blue2]M[/sky_blue2][light_sky_blue1]O[/light_sky_blue1][plum1]D[/plum1][orchid2]I[/orchid2] shell[/bold]] > "
            else:
                prompt_string = f"    [[bold][sky_blue2]M[/sky_blue2][light_sky_blue1]O[/light_sky_blue1][plum1]D[/plum1][orchid2]I[/orchid2] shell[/bold] in [bold orchid1]{self.project}[/bold orchid1]]> "
            return Prompt.ask(prompt_string).split(" ")

class Config:
    def __init__(self, config_file):
        self.config_file = config_file
        try:
            open(self.config_file, "r")
        except FileNotFoundError:
            with open(self.config_file, "w") as file:
                file.write("{}")
        with open(self.config_file, "r") as file:
            self.obj = json.loads(file.read())

    def write(self):
        with open(self.config_file, "w") as file:
            file.write(json.dumps(self.obj, indent=4, sort_keys=True))


def clear(self): 
    if(os.name != "posix"):
        os.system('cls')
    else:
            os.system('clear')

class Modi:
    def __init__(self, args=[], mode="module", loudness="norm"):
        self.env_home = os.getenv("HOME", "")
        global termtype
        self.console = Output(termtype, loudness)
        self.termtype = termtype
        self.logged_in = False
        try:
            file = open(f"{self.env_home}/.modi.json", "r")
            file.close()
        except:
            self.console.log("Config file not found, bootstrapping...", mtype="warning")
            with open(Path(f"{self.env_home}/.modi.json"), "w") as conf:
                filepath = Path(f"{self.env_home}/.modi_cache/")
                os.makedirs(Path(f"{self.env_home}/.modi_cache/"), exist_ok=True)
                json_conf = {"cache": {"path": str(filepath)}, "projects": {}}
                conf.write(json.dumps(json_conf))
        self.config = Config(Path(f"{self.env_home}/.modi.json"))
        self.site_prefix = ""
        if(os.name != "posix"):
            self.windows = True
            self.site_prefix = "/lib/site-packages/"
        else:
            self.windows = False
            self.site_prefix = f"/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages/"

        if(mode == "module"):
           pass 
        elif(mode == "interactive"): 
            if(self.termtype == "rich"):
                rich.print(f"    Starting [bold][sky_blue2]M[/sky_blue2][light_sky_blue1]O[/light_sky_blue1][plum1]D[/plum1][orchid2]I[/orchid2][/bold] {modi_version}")
            else:
                print(f"    Starting MODI {modi_version}")
            self.parseargs(args)
        elif(mode == "shell"):
            if(self.termtype == "rich"):
                rich.print(f"    Starting [bold][sky_blue2]M[/sky_blue2][light_sky_blue1]O[/light_sky_blue1][plum1]D[/plum1][orchid2]I[/orchid2][/bold] {modi_version}")
            else:
                print(f"    Starting MODI {modi_version}")
            self.shell()
        

    # PUBLIC methods, can be called from outside of class
    # | | |
    # v v v

    def try_import(self, module, pkg_name="", prompt=True):
        """Attempt to import a module. If not found, install locally and try again
        
        Args:
            module (str): The name of a Python module to try importing
            pkg_name (str): If given, the name of the PyPi package for the module, if different from the module name
            prompt (bool): Whether to prompt before installation.
        Returns:
            1: If after attempting download, the package could not be installed/imported
            0: If the module was imported successfully

        """
        import importlib
        if(pkg_name == ""):
            pkg_name = module
        try:
            importlib.import_module(module)
        except ImportError:
            res = 0
            if(prompt):
                style_str = self.__fmt_style(f"    The module ", 'bold gold1') + self.__fmt_style(f"'{module}'", 'bold light_sky_blue1') + self.__fmt_style(" could not be found. Install?", 'bold gold1')
                res = self.console.prompt_bool(style_str)
            if(res != True):
                return 1
            res = self.install_local([pkg_name])
            if res != 0:
                return 1
            try:
                importlib.import_module(module)
            except ImportError:
                self.console.log("Error: could not download and import module", mtype="error")
                return 1
            return 0

    def remote(self, args, shell=False):
        import requests
        if(len(args) == 0):
            self.console.log("Error: no valid command specified", mtype="error")
            return 1
        if("remote" not in self.config.obj.keys() and args[0] != "set"):
            self.console.log(f"You have not yet specified a remote to use. Please run {self.__fmt_code('modi.py remote set <url>')} first to select a remote repository.", mtype="error")
            return 1
        if(args[0] == "set"):
            if(len(args) < 2):
                return 1
            self.config.obj["remote"] = args[1]
            self.config.write()
            self.console.log(f"Set remote URL to {self.config.obj['remote']}")
        if(args[0] == "authenticate" and shell):
            self.logged_in = False
            username = ""
            password = ""
            if(len(args) > 1):
                if(args[1] == "logout"):
                    try:
                        self.console.log(f'Logged out user \'{self.config.obj["auth"]["username"]}\'', mtype="completion")
                        self.config.obj['auth'] = {}
                        self.logged_in = False
                        self.config.write()
                    except KeyError:
                        self.console.log(f'No logged-in user found, nothing to do...', mtype='warning')
                        return 1
                    return 0
            try:
                self.console.log(f"Logging in to remote {self.config.obj['remote']}")
                while not self.logged_in:
                    username = self.console.prompt(f"{self.__fmt_style('Enter username', 'bold gold1')}")
                    password = self.console.prompt(f"{self.__fmt_style('Enter password', 'bold light_sky_blue1')}", password=True)
                    url = f"{self.config.obj['remote']}/login/{username.strip()}"
                    headers = {'Authorization': password.strip()}
                    res = requests.get(url, headers=headers)
                    json_res = res.json()
                    if(res.status_code == 401):
                        self.console.log("Authentication unsuccessful. Try again or use ^C (Ctrl-C) to exit.", mtype="warning")
                    elif(res.status_code == 200):
                        self.console.log(f"Authentication successful, you are now logged in to '{self.config.obj['remote']}' as {self.__fmt_style(username, 'bold light_sky_blue1')}")
                        self.logged_in = True
                        self.config.obj['auth'] = {}
                        self.config.obj['auth']['username'] = username
                        self.config.obj['auth']['token'] = json_res['auth_code']
                        self.config.write()
            except KeyboardInterrupt:
                print()
                return 1
        elif(args[0] == "authenticate" and not shell):
            self.console.log("For security reasons, authentication from command-line is not supported", mtype="error")
            self.console.log(f"Please launch Modi Shell with {self.__fmt_code('modi.py shell')}, and run {self.__fmt_code('remote authenticate')} to log in.", mtype="error")
            return 1
        
        elif(args[0] == "publish"):
            if(len(args) <= 1):
                return 1
            start_time = time.perf_counter()
            package_name = args[1]
            valid_files = []
            cwd = Path(os.getcwd())
            for file in os.listdir(Path("./")):
                if package_name in file.split(".")[0] and file.split(".")[len(file.split(".")) - 1] in ["gz", "pkg", "zip"]:
                    valid_files.append(file)
            if(len(valid_files) == 0):
                self.console.log(f"Error: Could not find package '{package_name}' in current directory", mtype="error")
                return 1
            correct_file = ""
            current_dir = os.listdir(cwd)

            if(len(valid_files) > 1):
                self.console.log("There were multiple valid files to install", mtype="warning")
                correct_file = valid_files[self.console.prompt_selection(f"    Please select {self.__fmt_style('one', 'bold')}", valid_files) - 1]
            else:
                correct_file = valid_files[0]

            self.console.log(f"Uploading package {self.__fmt_style(correct_file, 'bold orchid1')} to {self.config.obj['remote']}")
            file_hdl = open(correct_file, 'rb')
            files = {'file': file_hdl.read()}
            url = f"{self.config.obj['remote']}/upload/{package_name}"
            headers = {'Authorization': self.config.obj['auth']['token'], 'X-Modi-Username': self.config.obj['auth']['username']}
            res = requests.put(url, files=files, headers=headers)
            finish_time = time.perf_counter()
            total_time = str(round(finish_time - start_time, 1))

            if(res.status_code == 401):
                self.console.log("Error: invalid authorisation token. Please logout and back in", mtype="error")
                return 1
            elif(res.status_code == 200):
                self.console.log(f"Successfully uploaded package {self.__fmt_style(correct_file, 'bold orchid1')} to remote {self.config.obj['remote']} in {total_time} seconds", mtype="completion")
                return 0
            else:
                self.console.log("Error: An unknown error occurred while uploading a package", mtype="error")
                return 1
        elif(args[0] == "bootstrap"):
            if(len(args) <= 1):
                return 1
            start_time = time.perf_counter()
            package_name = args[1]
            
            url = f"{self.config.obj['remote']}/package/{package_name}"
            self.console.log(f"Downloading package '{package_name}' from remote")
            self.__download_progress(url)
            finish_time = time.perf_counter()
            total_time = str(round(finish_time - start_time, 1))
            self.console.log(f"Successfully downloaded package {self.__fmt_style(package_name, 'bold light_sky_blue1')} from remote {self.config.obj['remote']} in {total_time} seconds", mtype="completion")
            return self.bootstrap(package_name, project_name=package_name)

    def gui(self, args):
        if(len(args) == 0):
            self.console.log(f"Error: full GUI not available yet. Please use {self.__fmt_code('modi.py gui minimal')} for now.", mtype="error")
            return 1
        if(args[0] == "full"):
            self.console.log(f"Error: full GUI not available yet. Please use {self.__fmt_code('modi.py gui minimal')} for now.", mtype="error")
            return 1
        elif(args[0] == "minimal"):
            from gui_minimal import ModiMinimalWindow, ModiInstallWorker, MLWorker, MLStripper, Package, fuzzy_search
            from PyQt6.QtWidgets import QApplication, QMainWindow
            app = QApplication([])
            window = ModiMinimalWindow()
            window.show()
            app.exec()



    def cd(self, directory):
        """Set the current working directory of the Python process

        Args:
            directory (str): the directory to switch to (can be in any format supported by pathlib)
        """
        os.chdir(Path(directory))

    def ls(self):
        """Print the contents of the CWD to stdout
        """
        if(self.console.project == ""):
            self.console.log("==== DIRECTORY LISTING ====", mtype="info")
            self.console.log(f"CWD: {os.getcwd()}", mtype="info")
        else:
            self.console.log("==== PROJECT LISTING ====", mtype="info")
            self.console.log(f"Project: {self.console.project}", mtype="info")
            self.console.log(f"In: {os.getcwd()}", mtype="info")
        for file in os.listdir(Path(os.getcwd())):
            self.console.log(file, mtype="info")

    def project(self, args):
        """Create, delete or bootstrap a MODI project
        
        Args:
            args (list): A list of commands to run. E.G: ["bootstrap", "from", "<pkg>"]

        Returns:
            1: if there was an error in project creation.
            0: if the project was succesfully created.
        """
        project_dir = ""
        project_name = ""
        if args[0] == "create" or args[0] == "bootstrap":
            project_name = ""
            project_ident = ""
            project_dir = ""
            if(len(args) == 1 or (args[0] == "bootstrap" and args[1] == "from")):
                project_name = self.console.prompt(f"{self.__fmt_style('Enter a project name', 'bold gold1')}")
                project_dir = str(Path(os.getcwd()))
            elif(len(args) == 2):
                project_name = args[1]
                project_dir = str(Path(os.getcwd()))
            elif(args[2] != "from"):
                project_name = args[1]
                project_dir = str(Path(args[2]))
            else:
                project_name = args[1]
                project_dir = str(Path(os.getcwd()))

            if("into" in args):
                try:
                   project_dir = str(Path(args[args.index("into") + 1]))
                except:
                    self.console.log("Error: 'into' specified but could not find directory.", mtype="error")
                    return 1
            proj_style_string = self.__fmt_style(project_name, 'bold light_sky_blue1')
            self.console.log(f"Creating project {proj_style_string} in {project_dir}")

            try:
                os.makedirs(project_dir, exist_ok=True)
            except:
                pass
            project_ident = project_name.replace(" ", "_").lower()
            
            proj_type = self.console.prompt(f"{self.__fmt_style('Enter a project type', 'bold gold1')}", choices=["module", "package"])
            self.console.log(f"Create a description for your project (type '@fi' to finish):")
            desc = []
            choice = ""
            while choice != "@fi":
                choice = self.console.prompt(f"{self.__fmt_style(' > ', 'bold light_sky_blue1')}")
                if(choice != "@fi"):
                    desc.append(choice)
            final_desc = ""
            for line in desc:
                final_desc += (line + "\n")

            deps = []

            if(os.path.exists(Path(f"{project_dir}/requirements.txt"))):
                self.console.log("Pulling dependencies from requirements.txt")
                with open(Path(f"{project_dir}/requirements.txt"), "r") as dep_file:
                    for line in dep_file.readlines():
                        deps.append(line.strip())

            self.config.obj["projects"][project_ident] = {"name": project_name, "directory": project_dir, "dependencies": [], "description": final_desc}
            self.config.write()
            proj_file = Config(Path(f"{project_dir}/modi.meta.json"))
            proj_file.obj["pkg_name"] = project_ident
            proj_file.obj["pkg_fullname"] = project_name
            proj_file.obj["dependencies"] = deps
            proj_file.obj["pkg_type"] = proj_type
            proj_file.obj["description"] = final_desc
            proj_file.write()
            with open(Path(f"{project_dir}/requirements.txt"), "w") as reqs:
                for dep in deps:
                    reqs.write(dep + "\n")

            style_string = self.__fmt_style(project_name, 'bold light_sky_blue1')
            self.console.log(f"Created project {style_string} in {project_dir}", mtype="completion")
            if("bootstrap" not in args):
                return 0
        
        elif args[0] == "unlist" or args[0] == "unlink":
            for proj_name in args[1:]:
                self.console.log(f"Unlisting project {proj_name}")
                if not self.console.prompt_bool(f"    {self.__fmt_style('This operation will not delete any files, but will remove the project from the local registry. Continue?', 'bold gold1')} "):
                    return 1
                if proj_name not in self.config.obj["projects"]:
                    self.console.log(f"Error: could not find project '{proj_name}'")
                    return 1
                config_backup = self.config.obj["projects"][proj_name]
                try:
                    os.remove(Path(f"{config_backup['directory']}/modi.meta.json"))
                except FileNotFoundError:
                    pass
                del self.config.obj["projects"][proj_name]
                self.config.write()
                style_string  = self.__fmt_style(proj_name, 'bold orchid1')
                self.console.log(f"Unlisted project {style_string} in {config_backup['directory']}", mtype="completion")
                if(proj_name == self.console.project):
                    self.console.project = ""
            return 0
        
        elif args[0] == "list":
            self.console.log("Modi project list:", mtype="info")
            for project in self.config.obj["projects"].values():
                proj_style = self.__fmt_style(project["name"], 'bold orchid1')
                one_line_desc = self.__fmt_style(project["description"].split("\n")[0], 'bold light_sky_blue1')
                self.console.log(f"{proj_style} in {project['directory']}", mtype="info")
                self.console.log(f"> {one_line_desc}", mtype="info")

        elif args[0] == "delete":
            if(len(args) < 2):
                return 1
            for proj_name in args[1:]:
                fmt_string = self.__fmt_style(proj_name, 'bold orchid1')
                self.console.log(f"Deleting project {fmt_string}")
                if not self.console.prompt_bool("    This operation cannot be undone. Continue?"):
                    return 1
                if proj_name not in self.config.obj["projects"]:
                    self.console.log(f"Error: could not find project '{proj_name}'")
                    return 1
                config_backup = self.config.obj["projects"][proj_name]
                try:
                    shutil.rmtree(config_backup["directory"])
                except FileNotFoundError:
                    self.console.log("Project directory not found, skipping deletion.", mtype="warning")
                del self.config.obj["projects"][proj_name]
                self.config.write()
                style_string  = self.__fmt_style(proj_name, 'bold orchid1')
                self.console.log(f"Deleted project {style_string} in {config_backup['directory']}", mtype="completion")
            return 0

        elif args[0] == "show":
            proj_data = {}
            try:
                with open("modi.meta.json", "r") as meta_file:
                    proj_data = json.loads(meta_file.read())
            except FileNotFoundError:
                self.console.log("Error: you are not currently in a valid Modi project", mtype="error")
                return 1
            fmt_string = self.__fmt_style(proj_data["pkg_fullname"], 'bold orchid1')
            self.console.log(f"Project data for {fmt_string}:", mtype="info")
            self.console.log(f"Dependencies: {proj_data['dependencies']}", mtype="info")
            self.console.log(f"Description:", mtype="info")
            for line in proj_data["description"].split("\n"):
                self.console.log(f"{self.__fmt_style(' > ', 'bold light_sky_blue1')}" + line, mtype="info")
            if f"{proj_data['pkg_name']}.modi.pkg" in os.listdir():
                fmt_string = self.__fmt_style(f"{proj_data['pkg_name']}.modi.pkg", 'bold orchid1')
                self.console.log(f"From: {fmt_string}", mtype="info")
            return 0
            
        if args[0] == "bootstrap":
            pkg_name = ""
            pwd = os.getcwd()

            if(len(args) < 3):
                return 1
            if(args[1] == "from"):
                pkg_name = args[2]
                if(self.termtype == "rich"):
                    pkg_name = self.console.prompt("[bold gold1]Enter a package name to install[/bold gold1]").replace(" ", "-")
                else:
                    pkg_name = self.console.prompt("    Enter a package name").replace(" ", "-")
            else:
                pkg_name = args[1]
            if(args[1] != "from" and len(args) < 4):
                return 1
            pkg_file = args[args.index("from") + 1]
            res = self.bootstrap(pkg_file, cwd=project_dir, project_name=project_name)
            return res
            
        elif args[0] == "goto":
            if(len(args) < 2):
                return 1
            pkg_name = args[1]
            try:
                path = Path(self.config.obj["projects"][pkg_name]["directory"])
            except:
                return 1
            try:
                self.cd(path)
            except FileNotFoundError:
                self.console.log(f"Error: broken project; could not change directory to {path}.", mtype="error")
                return 1
            self.console.project = pkg_name
            return 0

    def shell(self):
        """Wrap Modi.parseargs to provide an interface where a CLI is unavailable (such as IDLE)

        Returns:
            0: Always
        """
        cmdline = ""
        try:
            while True:
                cmdline = self.console.shell_prompt()
                if cmdline[0] in ["exit", "quit", "bye"]:
                    self.console.log("Bye!", mtype="completion")
                    return 0
                self.parseargs(cmdline, shell=True)
        except KeyboardInterrupt:
            print()
            self.console.log("Bye!", mtype="completion")

    def install_local(self, args, return_deps=False, no_projects=True, add_reqs=False):
        """Wrap Modi.install to install local packages more easily
        
        Args:
            *args: a list of packages to install locally from PyPi (variadic)

        Returns:
            1: if Modi.install failed to install any one of the requested packages
            0: if all packages downloaded and installed successfully
        """
        packages = []
        current_deps = []
        for arg in args:
            packages.append(arg)
        try:
            with open(Path("./requirements.txt"), "r") as req_file:
                current_deps = req_file.readlines()
                for dep in current_deps:
                    dep = dep.strip()
        except FileNotFoundError:
            pass
        
        if(add_reqs):
            with open(Path("./requirements.txt"), "w") as req_file:
                for pkg in packages:
                    if pkg not in current_deps:
                        current_deps.append(pkg)
                for dep in current_deps:
                    req_file.write(dep)

        inst_args = ["local"]

        for pkg in packages:
            inst_args.append(pkg)
        return self.install(inst_args, return_deps=return_deps, no_projects=no_projects)

    def install(self, args, return_deps=False, no_projects=True):
        """Install a package available from PyPi, either to the global cache or to the CWD

        Args:
            *args: a list of packages to install from PyPi, optionally with "local" as the first parameter which indicates that local mode should be used (variadic)

        Returns:
            1: if the method failed to install any one of the requested packages
            0: if all packages downloaded and installed successfully
        """

        self.total_deps = 0
        self.packages = []
        if("modi.meta.json" in os.listdir() and no_projects):
            self.console.log(f"Error: You are currently working in a Modi project. {self.__fmt_code('modi.py add <packages>')} must be used to install packages into a project", mtype="error")
            return 1
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
                if(args[1] == "auto" or args[1] == "all"):
                    try:
                        with open(Path("./requirements.txt"), "r") as reqs:
                            for line in reqs.readlines():
                                line = line.strip()
                                if(line[0] != "-" and line[0] != "." and line != ""):
                                    self.packages.append(line.split("=")[0])
                    except FileNotFoundError:
                        self.console.log("Error: could not find ./requirements.txt while attempting autoinstall", mtype="error")
                        return 1
                else:
                    self.packages = args[1:]
            else:
                return 1
        else:
            cwd = str(Path(self.config.obj["cache"]["path"]))
            self.packages = args
        self.prefix = cwd

        setup_py_queue = []
        pkg_count = len(self.packages)
        self.total_deps = 0
        start_time = time.perf_counter()
        pkgs_failed = 0

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
                    res = self.__install_pip(pkg)
                    count += 1
                    dep_count = len(glob.glob(str(Path(f"{self.prefix}/{self.site_prefix}/*[!info]")))) - count - self.total_deps
                    self.total_deps += dep_count
                    if(res == 0):
                        if(self.prefix == str(Path(os.getcwd()))):
                            self.console.log(f"Downloaded package '{pkg}' and {str(dep_count)} dependencies", mtype="completion")
                        else:
                            self.console.log(f"Installed package '{pkg}' and {str(dep_count)} dependencies", mtype="completion")
                    else:
                        setup_py_queue.append(pkg)

                else:
                    self.console.log("Using legacy setuptools mode, dependencies will have to be installed manually", mtype="warning")
                    self.console.log(f"{verb} package '{pkg}' with setuptools", mtype="message")
                    res = self.__install_setuptools(pkg)
                    if(res == 1 or pkg not in os.listdir(f"{self.prefix}/{self.site_prefix}")):
                        self.console.log("Error: failed to install package '" + pkg + "'", mtype="error")
                        pkgs_failed += 1
                    else:
                        if(local):
                            self.console.log(f"Downloaded and built package '{pkg}'", mtype="message")
                        else:
                            self.console.log(f"Installed package '{pkg}'", mtype="message")
            if(len(setup_py_queue) > 0):
                self.console.log("Some packages failed to install correctly, trying with setuptools", mtype="warning")
            for pkg in rich.progress.track(setup_py_queue, description="    Downloading & Building...", transient=True):
                self.console.log("Using legacy setuptools mode, dependencies will have to be installed manually", mtype="warning")
                self.console.log(f"{verb} package '{pkg}' with setuptools", mtype="message")
                res = self.__install_setuptools(pkg)
                if(res == 1 or pkg not in os.listdir(f"{self.prefix}/{self.site_prefix}")):
                    self.console.log("Error: failed to install package '" + pkg + "'", mtype="error")
                    pkgs_failed += 1
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
                    res = self.__install_pip(pkg)
                    if(res == 1):
                        setup_py_queue.append(pkg)
                else:
                    res = self.__install_setuptools(pkg)
                    if(res == 1):
                        self.console.log("Error: failed to install package " + pkg, mtype="error")
                        pkgs_failed += 1
                    else:
                        self.console.log(f"Installed package {pkg}", mtype="message")
        final_deps = []
        final_pkgs = []
        if(local):
            if(return_deps):
                final_deps, final_pkgs = self.__copy_local(str(Path(f"{os.getcwd()}/{self.site_prefix}")), "./", return_deps=True)
            else:
                self.__copy_local(str(Path(f"{os.getcwd()}/{self.site_prefix}")), "./")
            shutil.rmtree(Path("./lib"))
            try:
                shutil.rmtree(Path("./scripts"))
            except:
                pass
            try:
                shutil.rmtree(Path("./bin"))
            except:
                pass
        finish_time = time.perf_counter()
        total_time = str(round(finish_time - start_time, 1))
        pkg_count = str(pkg_count)
        keyword = "to Modi cache"
        package_desc = "packages"
        dep_desc = "dependencies"
        if(local):
            keyword = f"locally, to {self.prefix}"
        if(pkg_count == "1"):
            package_desc = "package"
        if(self.total_deps == 1):
            dep_desc = "dependency"
        elif(self.total_deps == 0):
            dep_desc = "dependencies"
            self.total_deps = "no"

        self.console.log(f"Installed {int(pkg_count) - pkgs_failed} {package_desc} and {self.total_deps} {dep_desc} {keyword} in {total_time} seconds", mtype="completion")
        if(return_deps):
            return final_deps, final_pkgs
        if(pkgs_failed > 0):
            self.console.log(f"Failed to install {pkgs_failed} package(s). Check the logs for details", mtype="warning")
            return 1
        return 0

    def help(self, name=""):
        """Print usage help information to stdout, for interactive-mode commands.
        
        Args:
            name (str): the name of a command to help with. Defaults to "", which shows basic help
        """
        self.console.log(f"{self.__fmt_style('MODI Help:', 'bold')}", mtype="info")
        if name not in ["install", "help", "remove", "build", "bootstrap", "setup", "project", "shell"]:
            self.console.log(f"- {self.__fmt_code('modi.py install [args]')}  : Installs one or more packages", mtype="info")
            self.console.log(f"- {self.__fmt_code('modi.py build [args]')}    : Build a Modi package in the CWD", mtype="info")
            self.console.log(f"- {self.__fmt_code('modi.py bootstrap [args]')}: Bootstraps a directory from the contents of a Modi package", mtype="info")
            self.console.log(f"- {self.__fmt_code('modi.py project [args]')}  : Create, manage, bootstrap and delete Modi projects", mtype="info")
            self.console.log(f"- {self.__fmt_code('modi.py help [cmd]')}      : Shows the help page, either this or the detailed view for cmd", mtype="info")
        elif name == "install":
            self.console.log(f"- {self.__fmt_code('modi.py install <package> [package] [...]')}         : Installs one or more packages to the global MODI cache (by default @ ~/.modi_cache)", mtype="info")
            self.console.log(f"  > {self.__fmt_code('modi.py install @<package> [package] [...]')}      : Same as above, but forcing use of the setuptools install method. Use if the previous option isn't working.", mtype="info")
            self.console.log(f"- {self.__fmt_code('modi.py install local <package> [package] [...]')}   : Installs one or more packages to the current working directory. This means they can be directly imported using `import <package>`", mtype="info")
            self.console.log(f"  > {self.__fmt_code('modi.py install local @<package> [package] [...]')}: Same as above, but forcing use of the setuptools install method. Use if the previous option isn't working.", mtype="info")
        elif name == "remove":
            self.console.log(f"- {self.__fmt_code('modi.py remove <package> [package] [...]')}        : Removes one or more packages from the global MODI cache.", mtype="info")
            self.console.log(f"  > {self.__fmt_code('modi.py remove local <package> [package] [...]')}: Removes one or more packages from the current working directory.", mtype="info")
            self.console.log(f"  > {self.__fmt_code('modi.py remove local all')}                      : Removes all packages and subdirectories in the CWD, leaving only python files (and some special directories such as `.git`", mtype="info")
        elif name == "build":
            self.console.log(f"- {self.__fmt_code('modi.py build freeze <output type> [pkg_name]')} : Builds a compressed archive in the format <output type> (either 'tar' or 'zip') from the contents of the CWD. The pkg_name will be prompted if it is not given", mtype="info")
            self.console.log(f"- {self.__fmt_code('modi.py build auto <output type> [pkg_name]')}  : Builds a compressed archive in the format <output type> (either 'tar' or 'zip') from the list of requirements in ./requirements.txt", mtype="info")
        elif name == "project":
            self.console.log(f"- {self.__fmt_code('modi.py project create [name] [directory]')}               : Creates a new project in the directory [directory] (if given, otherwise in CWD). The name will be prompted if not given.", mtype="info")
            self.console.log(f"- {self.__fmt_code('modi.py project delete <name>')}                           : Removes a project from Modi's config and deletes the directory it's located in. Will prompt before deletion.", mtype="info")
            self.console.log(f"- {self.__fmt_code('modi.py project unlist <name>')}                           : Removes a project from Modi's config, but keeps the directory it's located in.", mtype="info")
            self.console.log(f"- {self.__fmt_code('modi.py project goto <name>')}                             : In the Modi Shell, jumps to the directory of the specified project (equivalent to cd).", mtype="info")
            self.console.log(f"- {self.__fmt_code('modi.py project bootstrap <name> from <pkg>')}             : Creates a new project the same as self.__fmt_code('modi.py project create'), but also initialises it from a Modi package.", mtype="info")
            self.console.log(f"  > {self.__fmt_code('modi.py project bootstrap <name> from <pkg> into <dir>')}: Same as above, but use <dir> as the working/project directory.", mtype="info")
        elif name == "shell":
            self.console.log(f"- {self.__fmt_code('modi.py shell')} : Launches a shell, where all Modi commands (as well as some shell extras like `cd` and `ls`) are available without prefixing with 'modi.py'", mtype="info")
        elif name == "bootstrap":
            self.console.log(f"- {self.__fmt_code('modi.py bootstrap <pkg_name>')}: Removes all other files in the CWD (except modi.py and any archive files beginning with <pkg_name>) and bootstraps the project from a corresponding archive.")
            self.console.log(f" > e.g. {self.__fmt_code('modi.py bootstrap asciimatics')} would install a package from either 'asciimatics.zip', 'asciimatics.tar.gz' or (preferably) 'asciimatics.modi.pkg'.")
        elif name == "help":
            self.console.log(f"- {self.__fmt_code('modi.py help')}        : Shows the short help view for MODI.", mtype="info")
            self.console.log(f"  > {self.__fmt_code('modi.py help [cmd]')}: Shows detailed help for a specific command.", mtype="info")
        elif name == "demo":
            self.console.log(f"- {self.__fmt_code('modi.py demo [font]')}: Shows Modi's logo with PyFiglet + Rich, downloading if necessary. Optionally uses the specified PyFiglet font.", mtype="info")
        elif name == "logo":
            self.console.log(f"- {self.__fmt_code('modi.py logo [font]')}: Alias for {self.__fmt_code('modi.py demo [logo]')}", mtype="info")

    def logo(self, font="colossal"):
        """Show the Modi logo, as a demonstration for Modi's capabilities
        
        Args:
            font (str): a PyFiglet font to use for the demo
        Returns:
            1: If the function threw an error
            0: If the function ran successfully
        """
        self.console.log("Running Modi demo...", mtype="info")
        try:
            import pyfiglet
            import rich
        except ImportError:
            if not self.console.prompt_bool("    PyFiglet and Rich not found. Install?"):
                return 1
            if self.install_local(["pyfiglet", "rich"], no_projects=False, add_reqs=False) == 1:
                self.console.log("Could not install PyFiglet and Rich, exiting...", mtype="error")
                return 1
        import pyfiglet
        import rich
        import rich.markup
        lines_arr = []
        try:
            lbr = pyfiglet.figlet_format("[", font=font)
        except pyfiglet.FontNotFound:
            self.console.log("Error: invalid PyFiglet font specified", mtype="error")
            return 1
        m = pyfiglet.figlet_format("M", font=font)
        o = pyfiglet.figlet_format("O", font=font)
        d = pyfiglet.figlet_format("D", font=font)
        i = pyfiglet.figlet_format("I", font=font)
        rbr = pyfiglet.figlet_format("]", font=font)
        height = len(lbr.split("\n"))
        lbr = lbr.split("\n")
        m = m.split("\n")
        o = o.split("\n")
        d = d.split("\n")
        i = i.split("\n")
        rbr = rbr.split("\n")
        print()
        for j in range(height):
            lines_arr.append(f"[bold][grey100]{lbr[j]}[/grey100][sky_blue_2] {m[j]}[/sky_blue_2][light_sky_blue1] {o[j]}[/light_sky_blue1][plum1] {d[j]}[/plum1][orchid1] {i[j]}[/orchid1][grey100] {rbr[j]}[/grey100]")
        for line in lines_arr:
            self.console.log(line, mtype="info")
        return 0

    def heat(self, *args):
        """Heat from fire, fire from heat"""
        args = args[0]
        try:
            if(args[1] != "fire"):
                return 1
        except IndexError:
            return 1
        if(args[0] != "from"):
            return 1
        try:
            import pyfiglet
            import rich
        except ImportError:
            if not self.console.prompt_bool("    PyFiglet and Rich not found. Install?"):
                return 1
            if self.install_local(["pyfiglet", "rich"], no_projects=False, add_reqs=False) == 1:
                self.console.log("Could not install PyFiglet and Rich, exiting...", mtype="error")
                return 1
        import pyfiglet
        import rich
        import rich.markup
        colors_arr = ["bold light_sky_blue1", "bold light_sky_blue1", "bold pink1", "bold grey100", "bold pink1", "bold pink1", "bold light_sky_blue1", "grey100", "grey100", "grey100"]
        lines_arr = pyfiglet.figlet_format("Fire from Heat", font="roman", width=150).splitlines(False)
        self.console.log(len(lines_arr))
        i = 0
        for line in lines_arr:
            self.console.log(self.__fmt_style(line, colors_arr[i % 10]), mtype="info")
            i += 1


    def add(self, pkgs):
        """Wraps Modi.install to also add dependencies to modi.meta.json and requirements.txt

        Args:
            pkgs (list): A list of packages to add
        Returns:
            The result of Modi.install(pkgs)
        """
        req_pkgs = []
        current_deps = []
        proj_conf = {}
        try:
            with open("requirements.txt", "r") as reqs:
                current_deps = reqs.read().split("\n")
            with open("modi.meta.json", "r") as conf:
                proj_conf = json.loads(conf.read())
            for pkg in pkgs:
                if pkg in current_deps or pkg in proj_conf["dependencies"]:
                    self.console.log("Package already in project dependencies list.", mtype="warning")
                    if self.console.prompt_bool(f"    {self.__fmt_style('Do you want to continue installation?', 'bold gold1')}"):
                        req_pkgs.append(pkg)
                if pkg not in current_deps:
                    req_pkgs.append(pkg)
                if pkg not in proj_conf["dependencies"]:
                    proj_conf["dependencies"].append(pkg)
            with open("modi.meta.json", "w") as conf:
                conf.write(json.dumps(proj_conf, indent=4))
            with open("requirements.txt", "a") as reqs:
                for dep in req_pkgs:
                    reqs.write(dep)
        except:
            self.console.log("Error: Project files not found. Run 'modi.py project create' to create a new project in this directory", mtype="error")
        self.config.obj["projects"][proj_conf["pkg_name"]]["dependencies"] = proj_conf["dependencies"]
        self.config.write()
        self.install_local(req_pkgs, return_deps=False, no_projects=False, add_reqs=False)

    def parseargs(self, *args, shell=False):
        """Parse arguments and call appropriate functions within the class

        Args:
            *args (variadic str): A list of arguments, such as from sys.argv
            shell (bool): Whether to enable some additional convenienve functions such as ls and cd

        Returns:
            1: if there was an error with the arguments parsed
            Nothing: if a command was run
        """
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
        elif(args[0] == "logo" or args[0] == "demo"):
            if(len(args) > 1):
                self.logo(font=args[1])
            else:
                self.logo()
        elif(args[0] == "remote"):
            self.remote(args[1:], shell=shell)
        elif(args[0] == "build"):
            self.build(args[1:])
        elif(args[0] == "bootstrap" or args[0] == "setup"):
            self.bootstrap(args[1])
        elif(args[0] == "shell"):
            self.shell()
        elif(args[0] == "project"):
            self.project(args[1:])
        elif(args[0] == "add"):
            self.add(args[1:])
        elif(args[0] == "gui"):
            self.gui(args[1:])
        elif((args[0] == "ls" or args[0] == "dir") and shell):
            self.ls()
        elif((args[0] == "cd") and shell):
            self.cd(args[1])
        elif((args[0] == "heat") and shell):
            self.heat(args[1:])
        elif(args[0] == "self" and len(args) > 1):
            if(args[1] == "sync"):
                self.sync('modi')
        else:
            self.console.log("Error: no valid operation specified", mtype="error")
            return 1

    def build(self, args, freeze=False, mode="package", pkg_type="tar", pkg_name=""):
        """Build a package from the contents of the current working directory.
        
        Args:
            freeze (bool): Whether to freeze the CWD. If False, install packages from requirements.txt first.
            mode (str): "package" or "egg". Describes the type of file which will be produced - either a zipped version of the CWD, or a setuptools egg file.
            pkg_type (str): "tar" or "zip". If 'mode' is set to "package", describes the archive format which will be used.
            pkg_name (str): The name of the package to be produces
            args* (variadic): A string command which summarises the operation to be performed. Should only be used in interactive mode to parse a command line.
        Returns:
            1: If the package failed to build for any reason
            pkg_name: The path of the package relative to the CWD, if successfully built
        """
        mode = "package"
        if(args[0] == "freeze"):
            self.console.log("Building package from current working directory state")
            freeze = True
        elif(args[0] == "auto"):
            self.console.log("Building package from requirements.txt")
            freeze = False
        else:
            self.console.log("Error: invalid or no operation specified. Please use either 'auto' or 'freeze'", mtype="error")
            return 1
        if(len(args) > 1):
            pkg_type = args[1]
        if(len(args) > 2):
            pkg_name = args[2]
        packages = []
        final_deps, final_pkgs = [], []
        if(freeze):
            pass
        else:
            try:
                with open("requirements.txt", "r") as reqs:
                    for line in reqs.readlines():
                        line = line.strip()
                        if(line == ""):
                            continue
                        if(line[0] != "-" and line[0] != "."):
                            packages.append(line.split("=")[0])
            except FileNotFoundError:
                self.console.log("Error: 'auto' mode selected but could not find ./requirements.txt", mtype="error")
                return 1
            try:
                final_deps, final_pkgs = self.install_local(packages, return_deps=True, no_projects=False)
            except TypeError:
                self.console.log("Error: 'auto' mode selected, but ./requirements.txt didn't contain any valid packages", mtype="error")
                return 1

        current_working_dir = os.listdir(Path("./"))
        final_dirs = []
        requires_modi = False
        for file in current_working_dir:
            if(os.path.isdir(Path(f"./{file}")) and not (file[0] == "." or (file[0] == "_"))):
                final_dirs.append(file)
            elif("py" in file.split(".")[1:] and "modi" not in file.split(".")[0] and file[0] != "."):
                self.console.log(file)
                with open(Path(file), "r") as fd:
                    if("import modi" in fd.read()):
                        requires_modi = True
                final_dirs.append(file)
            elif(not os.path.isdir(f"./{file}")):
                if(':x-modi-build-requires:' in open(file, 'r').read()):
                    requires_modi = True
        if(requires_modi):
            final_dirs.append("./modi.py")
        if(pkg_name == ""):
            if(self.termtype == "rich"):
                pkg_name = self.console.prompt("[bold gold1]Enter a package name[/bold gold1]").replace(" ", "-")
            else:
                pkg_name = self.console.prompt("    Enter a package name").replace(" ", "-")
        style_string = self.__fmt_style(f"{pkg_name}", 'bold light_sky_blue1')
        self.console.log(f"Building package {style_string}")
        start_time = time.perf_counter()
        if(pkg_type == "tar"):
            comp_task = ""
            prog_bar = ""
            self.console.log(f"Mode 'tar' selected, building compressed package...")
            import tarfile
            filename = pkg_name
            try:
                os.mkdir(Path(f"./{pkg_name}"))
            except FileExistsError:
                pkg_name = f"{pkg_name}.modi-build"
                os.mkdir(Path(f"./{pkg_name}"))
            for file in final_dirs:
                try:
                    shutil.copy(Path(f"./{file}"), Path(f"./{pkg_name}/{file}"))
                except:
                    try:
                        shutil.copytree(Path(f"./{file}"), Path(f"./{pkg_name}/{file}"))
                    except:
                        self.console.log(f"Could not copy file '{file}' to compressed archive, skipping", mtype="warning")
            tar = tarfile.open(Path(f"./{filename}.tar.gz"), 'w:gz', compresslevel=4)
            tar.add(Path(f"./{pkg_name}"))
            tar.close()
            shutil.rmtree(Path(f"./{pkg_name}"))
            self.console.log("Finished building tar archive", mtype="completion")
        elif(pkg_type == "zip"):
            self.console.log("Mode 'zip' selected, building compressed package...")
            import zipfile
            filename = pkg_name
            try:
                os.mkdir(Path(f"./{pkg_name}"))
            except FileExistsError:
                pkg_name = f"{pkg_name}.modi-build"
                os.mkdir(Path(f"./{pkg_name}"))

            for file in final_dirs:
                try:
                    shutil.copy(Path(f"./{file}"), Path(f"./{pkg_name}/{file}"))
                except:
                    try:
                        shutil.copytree(Path(f"./{file}"), Path(f"./{pkg_name}/{file}"))
                    except:
                        self.console.log(f"Could not copy file '{file}' to compressed archive, skipping", mtype="warning")
            zip_file = zipfile.ZipFile(Path(f"./{filename}.zip"), mode="w")
            self.__zip_recursive(str(Path(f"./{pkg_name}")), zip_file)
            zip_file.close()
            shutil.rmtree(Path(f"./{pkg_name}"))
        elif(pkg_type == "modi"):
            self.console.log(f"Mode 'modi' selected, building compressed MODI package...")
            import tarfile
            filename = pkg_name
            try:
                os.mkdir(Path(f"./{pkg_name}"))
            except FileExistsError:
                pkg_name = f"{pkg_name}.modi_build"
                os.mkdir(Path(f"./{pkg_name}"))

            meta_obj = {"pkg_name": pkg_name, "dependencies": [*final_pkgs]}
            json_obj = json.dumps(meta_obj, sort_keys=True, indent=4)
            if(not os.path.exists(Path("./modi.meta.json"))):
                with open(Path(f"./{pkg_name}/modi.meta.json"), "w") as meta_inf:
                    meta_inf.write(json_obj)
            else:
                shutil.copy("modi.meta.json", Path(f"./{pkg_name}/modi.meta.json"))
                self.console.log("Copied existing project config to tarfile")
            for file in final_dirs:
                try:
                    shutil.copy(Path(f"./{file}"), Path(f"./{pkg_name}/{file}"))
                except:
                    try:
                        shutil.copytree(Path(f"./{file}"), Path(f"./{pkg_name}/{file}"))
                    except:
                        self.console.log(f"Could not copy file '{file}' to compressed archive, skipping", mtype="warning")
            tar = tarfile.open(Path(f"./{filename}.modi.pkg"), 'w:gz', compresslevel=4)
            tar.add(Path(f"./{pkg_name}"))
            tar.close()
            shutil.rmtree(Path(f"./{pkg_name}"))
            self.console.log("Finished building modi package", mtype="completion")
        if(args[0] == "auto"):
            files_to_delete = [*final_deps, *final_pkgs]
            self.console.log("Cleaning up local directory...")
            self.remove(["local", *files_to_delete], warn=False)
            style_string = self.__fmt_style(f"{pkg_name}", 'bold light_sky_blue1')
        finish_time = time.perf_counter()
        total_time = round(finish_time - start_time, 1)
        self.console.log(f"Finished building package {style_string} in {total_time} seconds", mtype="completion")
        return 0

    def sync(self, package_name):
        import requests
        """Update a package from Modi Cloud

        Args:
            package_name (str): the name of the package to install from remtoe

        Returns:
            0: if the package installed successfully
            1: if there was an error during extraction
        """
        start_time = time.perf_counter()
        
        url = f"{self.config.obj['remote']}/package/{package_name}"
        self.console.log(f"Downloading package '{package_name}' from remote")
        self.__download_progress(url)
        finish_time = time.perf_counter()
        total_time = str(round(finish_time - start_time, 1))
        self.console.log(f"Successfully downloaded package {self.__fmt_style(package_name, 'bold light_sky_blue1')} from remote {self.config.obj['remote']} in {total_time} seconds", mtype="completion")
        return self.bootstrap(package_name, cleanup=False)


    def bootstrap(self, package_name, cwd="", project_name="", cleanup=True):
        """Bootstrap a project from a .zip, .tar.gz or (ideally) .modi.pkg file to the CWD
        
        Args:
            package_name (str): the name of the package to install, without extension

        Returns:
            0: if the archive extracted successfully
            1: if there was an error during archive extraction
        """
        valid_files = []
        self.console.log(f"Bootstrapping project {package_name}")
        if(cwd == ""):
            cwd = Path(os.getcwd())
        for file in os.listdir(Path("./")):
            if package_name in file.split(".")[0] and file.split(".")[len(file.split(".")) - 1] in ["gz", "pkg", "zip"]:
                valid_files.append(file)
        if(len(valid_files) == 0):
            self.console.log(f"Error: Could not find package {package_name} in current directory", mtype="error")
            return 1
        correct_file = ""
        current_dir = os.listdir(cwd)
        try:
            current_dir.remove("modi.py")
        except:
            pass
        try:
            current_dir.remove("modi.meta.json")
        except:
            pass
        for file in valid_files:
            try:
                current_dir.remove(file)
            except ValueError:
                pass
        if(len(valid_files) > 1):
            self.console.log("There were multiple valid files to install", mtype="warning")
            correct_file = valid_files[self.console.prompt_selection(f"    Please select {self.__fmt_style('one', 'bold')}", valid_files) - 1]
        else:
            correct_file = valid_files[0]

        if(len(current_dir) > 0 and cleanup):
            self.console.log(f"The directory {cwd} contains files other than modi.py and packages.", mtype="warning") 
            self.console.log("If you choose to continue, they will be deleted.", mtype="warning")
            choice = self.console.prompt_bool("    Continue?")
            if(not choice):
                return 1
        if cleanup:
            for file in current_dir:
                try:
                    os.remove(Path(f"{cwd}/{file}"))
                except IsADirectoryError:
                    shutil.rmtree(Path(f"{cwd}/{file}"))
                except PermissionError:
                    self.console.log("Could not remove file {file} because of a permissions error", mtype="warning")
                    pass
            if(Path(os.getcwd()) == cwd):
                shutil.copy(Path(f"{cwd}/modi.py"), Path(f"{cwd}/modi.py.bak"))

        file_style_string = self.__fmt_style(correct_file, 'bold orchid1')
        package_style_string = self.__fmt_style(package_name, 'bold light_sky_blue1')
        self.console.log(f"Extracting project {package_style_string} from {file_style_string}")
        start_time = time.perf_counter()
        file_ext = correct_file.split(".")[len(correct_file.split(".")) - 1]
        file_meta = ""
        if(file_ext == "zip"):
            import zipfile
            zip_hdl = zipfile.ZipFile(Path(f"./{correct_file}"))
            zip_hdl.extractall(Path(f"{cwd}"))
            zip_hdl.close()
            self.console.log(f"{self.__fmt_style('Zip archive', 'bold gold1')} selected, cannot auto-generate requirements.txt", mtype="warning")
        else:
            import tarfile
            tar_hdl = tarfile.open(Path(f"./{correct_file}"))
            tar_hdl.extractall(Path(f"{cwd}"))
            if(file_ext != "pkg"):
                self.console.log(f"{self.__fmt_style('Tar-GZ archive', 'bold gold1')} selected, cannot auto-generate requirements.txt", mtype="warning")

        for file in os.listdir(Path(f"{cwd}/{package_name}")):
            if os.path.exists(Path(f"{cwd}/{file}")):
                try:
                    shutil.rmtree(Path(f"{cwd}/{file}"))
                except NotADirectoryError:
                    os.remove(Path(f"{cwd}/{file}"))
            try:
                shutil.copytree(Path(f"{cwd}/{package_name}/{file}"), Path(f"{cwd}/{file}"))
            except NotADirectoryError:
                shutil.copy(Path(f"{cwd}/{package_name}/{file}"), Path(f"{cwd}/{file}")) 

        shutil.rmtree(Path(f"{cwd}/{package_name}"))
        if cleanup:
            if(Path(os.getcwd()) == cwd):
                shutil.copy(Path(f"{cwd}/modi.py.bak"), Path(f"{cwd}/modi.py"))
                os.remove(Path(f"{cwd}/modi.py.bak"))
        try:
            os.chmod("modi.py", 0o755)
        except:
            pass

        if(file_ext == "pkg"):
            try:
                with open(Path(f"{cwd}/modi.meta.json")) as meta_file:
                    file_meta = json.loads(meta_file.read())
            except:
                self.console.log("Invalid or missing meta-information file, cannot write requirements.txt", mtype="warning")
        if(project_name != ""):
            file_meta["pkg_name"] = project_name.replace(' ', '-')
            file_meta["pkg_fullname"] = project_name
        if not cleanup:
            with open(Path(f"{cwd}/modi.meta.json"), "w") as meta_file:
                meta_file.write(json.dumps(file_meta, indent=4))
        os.remove(correct_file)
        final_deps = [*file_meta["dependencies"]]
        if cleanup:
            if(file_meta != ""):
                with open(Path(f"{cwd}/requirements.txt"), "w") as req_file:
                    for dep in final_deps:
                        req_file.write(dep)
        finish_time = time.perf_counter()
        total_time = round(finish_time - start_time, 1)
        print_string = ""
        verb = "bootstrapped"
        if not cleanup:
            verb = "synced"
        if(file_ext == "pkg" and project_name != ""):
            proj_string = self.__fmt_style(project_name, 'bold light_sky_blue1')
            print_string = f"Successfully {verb} package '{package_name}' and {len(final_deps)} dependencies into project {proj_string} in {total_time} seconds"
        elif(file_ext == "pkg"):
            print_string = f"Successfully {verb} package '{package_name}' and {len(final_deps)} dependencies in {total_time} seconds"
        else:
            print_string = f"Successfully {verb} package {package_name} and all dependencies in {total_time} seconds"
        self.console.log(print_string, mtype="completion")
        return 0
        

    def remove(self, args, local=False, warn=True):
        """Remove one or more packages from CWD or global cache

        Args:
            local (bool): Whether to operate on only the CWD. Allows use of 'all' in *args
            *args (variadic): A list of packages to remove. If 'local' is True and args[2] is 'all', remove all subdirectories in the CWD
        Returns:
            0: Always, even if some packages failed to delete.
        """
        self.packages = []
        self.console.log("Removing packages", mtype="warning")
        start_time = time.perf_counter()
        if(args[0] == "local"):
            local = True
            if(len(args) >= 2):
                if(args[1] == "all"):
                    if(warn):
                        if not self.console.prompt_bool(f"    Warning: this is a potentially destructive action.\n    Running {self.__fmt_code('modi.py remove local all')} will delete all subdirs in this project. Continue?"):
                                return 1
                    for filename in os.listdir(Path("./")):
                        if "." in filename:
                            if(filename != "requirements.txt" and filename.split(".")[len(filename.split(".")) - 1] != "py" and "modi" not in filename and ".tar" not in filename and ".zip" not in filename):
                                try:
                                    os.remove(Path(f"./{filename}"))
                                except PermissionError:
                                    pass
                                except IsADirectoryError:
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
            self.prefix = self.config.obj["cache"]["path"]
        pkg_count = len(self.packages)
        for pkg in self.packages:
            for fd in os.listdir(Path(f"{self.prefix}")):
                if pkg in fd:
                    try:
                        shutil.rmtree(Path(f"{self.prefix}/{fd}"))
                    except NotADirectoryError:
                        os.remove(Path(f"{self.prefix}/{fd}"))
            if(local):
                for fd in os.listdir(Path(f"{self.prefix}/")):
                    if pkg in fd:
                        try:
                            shutil.rmtree(Path(f"{self.prefix}/{fd}"))
                        except:
                            os.remove(Path(f"{self.prefix}/{fd}"))
        end_time = time.perf_counter()
        total_time = str(round(end_time - start_time, 1))
        self.console.log(f"Removed {str(pkg_count)} packages in {total_time} seconds", mtype="completion")
        return 0



    # PRIVATE methods. These should NOT be called directly, they will be invoked when needed
    # | | |
    # v v v

    def __download_progress(self, url, file=None):
        pkg_name = url.split('/')[len(url.split('/')) - 1]
        if file != None:
            filename = file
        else:
            filename = pkg_name + ".modi.pkg"

        if(self.termtype == "rich"):
            res = requests.get(url, stream=True)
            with open(filename, 'wb') as fd:
                for chunk in rich.progress.track(res.iter_content(chunk_size=128), description=f"    Downloading {self.__fmt_style(pkg_name, 'bold orchid1')}...", total=int(res.headers['Content-Length']) / 128):
                    fd.write(chunk)
        else:
            res = requests.get(url, stream=True)
            prev_blocks = 0
            blocks_done = 0
            blocks_todo = 50
            chunks_total = int(res.headers['Content-Length']) / 128
            chunks_done = 0
            sys.stdout.write(f"    Downloading '{pkg_name}': [{'█' * blocks_done}{' ' * blocks_todo}] {blocks_done * 2}%")
            with open(filename, 'wb') as fd:
                for chunk in res.iter_content(chunk_size=128):
                    chunks_done += 1
                    blocks_done = int((chunks_done / chunks_total) * 50)
                    blocks_todo = 50 - blocks_done
                    if prev_blocks != blocks_done:
                        prev_blocks = blocks_done
                        sys.stdout.write(f"\rDownloading '{pkg_name}': [{'█' * blocks_done}{' ' * blocks_todo}] {blocks_done * 2}%\r")

    def __zip_recursive(self, path, zip_handle):
        for root, dirs, files in os.walk(path):
            for file in files:
                zip_handle.write(os.path.join(root, file))
        
    def __copy_local(self, path, dest, return_deps=False):
        dest_files = os.listdir(dest)
        dependencies = []
        packages = []
        loop_var = []
        if(self.termtype == "rich" and self.console.loudness == "norm"):
            loop_var = rich.progress.track(os.listdir(path), description="    Installing...", transient=True)
        else:
            loop_var = os.listdir(path)
        for fd in loop_var:
            pkg_type = "dependency"
            if "info" not in fd and "egg" not in fd and "pth" not in fd:
                if(fd in self.packages):
                    pkg_type = "package"
                    packages.append(fd)
                if("." in fd):
                    pkg_type = "file dependency"
                    dependencies.append(fd)
                if(fd not in dest_files):
                    if(pkg_type == "dependency"):
                        dependencies.append(fd)
                    self.console.log(f"Installing {pkg_type} '{fd}'")
                try:
                    shutil.copytree(Path(f"{path}/{fd}"), f"{dest}/{fd}")
                except NotADirectoryError:
                    try:
                        shutil.copy(Path(f"{path}/{fd}"), f"{dest}/{fd}")
                    except FileExistsError:
                        pass
                    except shutil.SameFileError:
                        pass
                except FileExistsError:
                    pass
            elif "egg" in fd and "info" not in fd and "pth" not in fd:
                copy_list = []
                if(not os.path.isdir(Path(f"{path}/{fd}"))):
                    import zipfile
                    egg_zip = zipfile.ZipFile(Path(f"{path}/{fd}"), "r")
                    os.makedirs(Path(f"{path}/temp"), exist_ok=True)
                    egg_zip.extractall(str(Path(f"{path}/temp")))
                    egg_zip.close()
                    os.remove(Path(f"{path}/{fd}"))
                    shutil.copytree(Path(f"{path}/temp/{fd.split('-')[0]}"), Path(f"{path}/{fd.split('-')[0]}"))
                    shutil.rmtree(Path(f"{path}/temp"))
                    file = fd.split('-')[0]
                    if(file not in dest_files):
                        if(file in self.packages):
                            pkg_type = "package"
                        self.console.log(f"Installing {pkg_type} '{file}'")
                    try:
                        shutil.copytree(Path(f"{path}/{file}"), f"{dest}/{file}")
                    except NotADirectoryError:
                        try:
                            shutil.copy(Path(f"{path}/{file}"), f"{dest}/{file}")
                        except FileExistsError:
                            pass
                    except FileExistsError:
                        pass
                    break

                    
                for file in os.listdir(Path(f"{path}/{fd}")):
                    if file != "EGG-INFO":
                        copy_list.append(file)
                for file in copy_list:
                    if(file not in dest_files):
                        if(file in self.packages):
                            pkg_type = "package"
                        self.console.log(f"Installing {pkg_type} '{file}'")
                    try:
                        shutil.copytree(Path(f"{path}/{fd}/{file}"), f"{dest}/{file}")
                    except NotADirectoryError:
                        try:
                            shutil.copy(Path(f"{path}/{fd}/{file}"), f"{dest}/{file}")
                        except FileExistsError:
                            pass
                    except FileExistsError:
                        pass
            else:
                pass
        if(return_deps):
            return dependencies, packages
    
    def __fmt_style(self, text, style):
        if(self.termtype == "rich"):
            return f"[{style}]{text}[/{style}]"
        else:
            return text
    
    def __fmt_code(self, text, lang="modi"):
        cmd_list = text.split(" ")
        fmt_string = ""
        i = 0
        if(self.termtype == "plain"):
            return f"`{text}`"
        if(lang != "modi"):
            import rich.syntax
            return Syntax(text, lang)
        for arg in cmd_list:
            if("[" in arg and "]" in arg):
                fmt_string += f" [bold][[dark_sea_green2]{arg[1:(len(arg) - 1)]}[/dark_sea_green2]][/bold]"
            elif("<" in arg and ">" in arg):
                fmt_string += f" [bold]<[light_sky_blue1]{arg[1:(len(arg) - 1)]}[/light_sky_blue1]>[/bold]"
            elif(arg == "all" or arg == "auto"):
                fmt_string += f" [bold dark_sea_green2]{arg}[/bold dark_sea_green2]"
            elif(i == 0):
                fmt_string += f"[bold light_sky_blue1]{arg}[/bold light_sky_blue1]"
            elif("\"" in arg):
                fmt_string += f" [gold1]{arg}[/gold1]"
            else:
                fmt_string += f" [plum1]{arg}[/plum1]"
            i += 1
        return f"[on grey15]{fmt_string}[/on grey15]"



    def __install_pip(self, pkg):
        current_env = os.environ.copy()
        current_env["PYTHONPATH"] = str(Path(self.prefix) / Path(self.site_prefix))
        if(os.name != "posix"):
            inst_result = subprocess.run(f"py -m pip install --disable-pip-version-check --quiet --ignore-installed --no-warn-script-location {pkg} --prefix \"{self.prefix}\"", env=current_env, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        else:
            inst_result = subprocess.run(f"'{sys.executable}' -m pip install --quiet --ignore-installed --no-warn-script-location {pkg} --prefix {self.prefix}", env=current_env, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        if(inst_result.returncode != 0):
            self.console.log(f"Installing package {pkg} failed, adding to setuptools queue", mtype="warning")
            return 1
        else:

            return 0
    
    def __install_setuptools(self, pkg):
        if(not os.path.exists(Path(f"{self.prefix}{self.site_prefix}"))):
            path = Path(f"{self.prefix}{self.site_prefix}")
            path.mkdir(parents=True)
        pkg_json_data = ""
        try:
            with urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json") as res:
                pkg_json_data = res.read().decode("UTF-8")
        except urllib.error.HTTPError:
            return 1
        pkg_json_obj = json.loads(pkg_json_data)
        package_url = ""
        for url in pkg_json_obj["urls"]:
            if url["packagetype"] == "sdist" and url["python_version"] == "source":
                package_url = url["url"]
        pkg_version = pkg_json_obj["info"]["version"]

        try:
            with urllib.request.urlopen(package_url) as package_req:
                with open(f"{pkg}-{pkg_version}.tar.gz", "wb") as tarf:
                    tarf.write(package_req.read())
        except:
            self.console.log(f"Error: could not resolve source download for package '{pkg}'", mtype="error")
            return 1
        tarball = tarfile.open(f"{pkg}-{pkg_version}.tar.gz", mode='r:gz')
        tarball.extractall(f".")
        tarball.close()
        os.remove(f"{pkg}-{pkg_version}.tar.gz")
        current_env = os.environ.copy()
        current_env["PYTHONPATH"] = str(Path(self.prefix) / Path(self.site_prefix))
        cwd = os.getcwd()
        os.chdir(Path(f"./{pkg}-{pkg_version}"))
        inst_result = 1
        if(self.windows):
            inst_result = subprocess.run(f"py ./setup.py --quiet install --prefix \"{self.prefix}\"", env=dict(os.environ, PYTHONPATH=str(Path(f"{self.prefix}/{self.site_prefix}"))), shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        else:
            inst_result = subprocess.run(f"{sys.executable} ./setup.py --quiet install --prefix {self.prefix}", env=current_env, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    


if __name__ == "__main__":
    if check_IDLE():
        modi_instance = Modi(args=sys.argv[1:], mode="shell")
    else:
        modi_instance = Modi(args=sys.argv[1:], mode="interactive")
