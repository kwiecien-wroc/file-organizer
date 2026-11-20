# File Organizer

A command-line tool for organizing files by extension and removing identical files.

## Installation

Python 3.13 or newer is required. You can run the program without installation from the project directory:

```powershell
python main.py INPUT_DIRECTORY OUTPUT_DIRECTORY
```

To install the `file-organizer` command:

```powershell
python -m pip install .
```

## Organizing Files

The first time each extension is encountered, the program asks for a folder in the output directory. The choice is remembered for the duration of the run; multiple extensions can use the same folder. Subdirectories in the source are scanned recursively. If the output directory is inside the source directory, it is skipped. When filenames conflict, the file receives a UUID suffix before the extension.

```powershell
file-organizer "C:\Archive" "C:\Sorted"
```

## Removing Duplicates

Files are compared using SHA-256. The program displays all duplicate groups before asking for confirmation. One copy from each group is kept, and the paths of removed and kept files are appended to a log next to the scanned directory.

```powershell
python main.py --duplicates "C:\Archive"
```

You can provide a custom log path with the `--log-file` option:

```powershell
python main.py --duplicates "C:\Archive" --log-file "C:\reports\duplicates.log"
```

## Tests

Run the regression tests with:

```bash
python -m unittest discover -s tests -v
```