# Python example guide
This README will guide you through the setup process as well as how to run the different examples. 

## Requirements
1. python >= 3.12
2. See top folder README for more
3. Add git to the environment variables
4. A C++ compiler for building miniaudio (MP3/FLAC streams)
5. First time setup, either create a file called slm_ip and the root of your project and input your slm ip inside. It's also possible to uv run one of the examples and you will be prompted to type your slm ip and slm_ip will be created at the same folder as your pyproject.toml file.
    Add slm_ip to your .gitignore. If examples can't connect to your slm check the slm_ip file and see if it's the correct ip address.


It is recommended to install VSCode, Sublime Text 3, or similar to run and edit the code. To not break any Python installation it is recommended to use either a docker or a Python virtual environment to run the test, see references.

## Setup and how to run an example

### If you're using uv

To use the program using uv run the following command in the terminal

```
uv sync
```
This creates a `.venv` folder and installs everything into it. You do not need to activate it, `uv run` uses it automatically.

Then to run the examples use the command

```
uv run '.\01 - Getting device information.py'
```

### If you're using pip

First create and activate a virtual environment, so the packages are not installed into your system Python:

Windows

```
python -m venv .venv
.venv\Scripts\activate
```
Mac and Linux
```
python -m venv .venv
source .venv\bin\activate
```
On macOS and Linux the second command is `source .venv/bin/activate` instead. Once active, the environment name is shown in the terminal prompt. Use `deactivate` to leave it again.

To run the given examples must different Python modules be installed. To do this run the following two commands in a given terminal
```
python -m pip install -r requirements.txt
python -m pip install .
```
where python is your python environment, change this if e.g. a virtual environment is wanted or if multiple python versions are installed. It is now possible to run all of the examples using a terminal as
```
python "01 - Getting device information.py"
```

## Structure
This example packages consist of multiple examples where the level of complexity increases through the examples resulting in real-time streaming of LAeq. Some of the later examples will have different functions in common. Those are placed in the HelpFunctions folder.
To ease the handling of the data streamed from the device are Kaitai structs used. See references. The needed files to run the examples are already compiled and a part of this example package.

## References
1. [How to setup Python virtual environments.](https://docs.python.org/3/library/venv.html)
2. [Kaitai Struct documentation](https://kaitai.io/)
