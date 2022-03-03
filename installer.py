#!/usr/bin/env python3

print("    ==| [MODI] Installer v1.0 |==    ")

import urllib.request
import sys
import subprocess

component_list = ["modi"]

def install_component(name):
    try:
        url = f"https://jacobtye.dev/modi/{name}.py"
        urllib.request.urlretrieve(url, f'./{name}.py')
        print(f"    Successfully downloaded component '{name}'")
    except:
        print(f"    Error: Failed to install component '{name}'")
        return 1

print("    Downloading required component 'modi'")
install_component('modi')

if(input("    Install optional dependency 'rich' for 'modi' [Y/n]: ").lower() in ["y", ""]):
    try:
        import modi
        modi_inst = modi.Modi()
        modi_inst.install_local(['rich'], no_projects=False)
    except:
        print("    Error: failed to import the Modi library. Maybe it didn't download correctly?")
        sys.exit(1)

if(input("    Install optional component 'gui_minimal' [Y/n]: ").lower() in ["y", ""]):
    component_list.append("gui_minimal")
    install_component("gui_minimal")

if(input("    Install optional dependencies 'numpy' and 'PyQt6' for 'gui_minimal' [Y/n]: ").lower() in ["y", ""]):
    try:
        import modi
        modi_inst = modi.Modi()
        modi_inst.install_local(['rich'], no_projects=False)
    except:
        print("    Error: failed to import the Modi library. Maybe it didn't download correctly?")
        sys.exit(1)

if(input("    Done installing Modi. Make sure to run 'modi self sync' to update.\n    Start a shell now? [Y/n]: ").lower() in ["y", ""]):
    subprocess.run([f"{sys.executable}", "./modi.py", "shell"])
