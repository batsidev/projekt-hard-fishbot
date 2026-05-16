# MT2 Py-Fisher

This is a Python project that includes functionalities for interacting MT2 game window for in-game fishing. It also supports in-game message detection and handling messages in the queue.

## Structure

The project has the following structure:

- `fisher.py`: Main script.
- `desktop_launcher.py`: Windows desktop GUI launcher for starting and stopping `fisher.py`.
- `media/`: Directory for media files.
- `task_scheduler/`: Contains scripts for handling tasks and messages.
  - `ingame_message_handler.py`: Handles in-game messages.
  - `message_queue_handler.py`: Handles message queues.
  - `scheduler.py`: Handles task scheduling.
- `test/`: Contains test scripts.
  - `detect-color.py`: Test script for color detection.
  - `request.py`: Test script for handling requests.
- `utils/`: Contains utility scripts.
  - `keyboard.py`: Handles keyboard interactions.


## Setup

To set up the project, install the required Python packages:

```sh
pip install -r requirements.txt
```

## Usage
To run the main script, use the following command:

```sh
python fisher.py
```

## Desktop launcher

The project includes a small PySide6 desktop launcher for Windows. It starts and stops `fisher.py`, shows stdout and stderr logs in real time, and plays a notification sound when the log line contains `New message detected`.

Install the project dependencies first:

```sh
pip install -r requirements.txt
```

Start the GUI with:

```sh
python desktop_launcher.py
```

To build a standalone Windows `.exe`, install PyInstaller and run it from the project root:

```sh
pip install pyinstaller
pyinstaller --onefile --windowed desktop_launcher.py
```

The generated executable will be placed in the `dist/` directory.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License
MIT
