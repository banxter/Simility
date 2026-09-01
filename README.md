# Simility

> *A macOS-friendly desktop utility for reviewing groups of similarly named files and safely clearing out versions you no longer need.*

Built with Python and PyQt6.

## Highlights

- Find files with similar filename beginnings, with an adjustable similarity threshold.
- Scan only the selected folder or include all child folders.
- Review files in expandable groups, sorted newest first.
- See each file's location, size, and modified date.
- Select every result, only older versions, or invert the current selection.
- Move selected files to the macOS Trash instead of permanently deleting them.
- Move selected files to any destination folder you choose.
- Switch between polished Light and Dark appearances.
- Automatically restore your preferred folder, layout, search options, and theme.

## Workflow

1. Choose a folder.
2. Set the filename similarity percentage.
3. Search and review matching groups.
4. Select unwanted files.
5. Move them to Trash or another folder.

## Features

### Similar-name detection

Files are grouped when the common beginning of their names reaches the configured similarity percentage for *both* filenames. Extensions are excluded from matching, and comparisons are case-insensitive.

For example, at the default 30% similarity, files such as `Report_January.pdf`, `Report_February.pdf`, and `Report_March.xlsx` can appear in the same group even though their names have different lengths.

- Default similarity: 30%
- Adjustable range: 1% to 100%
- Filename extensions do not affect grouping.
- `.DS_Store` files are always ignored.
- Only groups with two or more matching files are shown.

### Search scope

Use **Include Sub Folders** to control where the app searches:

| **Setting** | **Behavior**                                           |
|-----------|------------------------------------------------------|
| Enabled     | Searches the chosen folder and all nested folders.     |
| Disabled    | Searches only files directly inside the chosen folder. |

### Results list

Matching files appear in expandable groups. Every group title is bold and each group's files are sorted by **Date Modified**, with the newest file at the top.

The resizable table includes:

| **Column**    | **Description**                   |
|-------------|---------------------------------|
| File          | Filename and selection checkbox   |
| Location      | Folder containing the file        |
| Size          | File size in a readable format    |
| Date Modified | Local last-modified date and time |

Drag any table header divider to resize its column.

### Selection controls

The bottom action bar provides fast ways to prepare a cleanup:

| **Control**            | **What it does**                                        |
|----------------------|-------------------------------------------------------|
| Select All Results     | Selects every file in every visible group.              |
| Select All Older Files | Selects every file except the newest one in each group. |
| Reverse Selection      | Inverts the selection state of every visible file.      |
| Clear Selection        | Clears every selected file.                             |

You can also select an entire group or make individual file selections with the checkboxes.

### Safe file actions

The app never deletes selected files permanently.

- Move to Trash sends selected files to the macOS Trash after confirmation, so they can be restored later if necessary.
- Move to Another Folder lets you choose a destination folder, confirms the action, and then moves the selected files there.
- To avoid accidental data loss, a file is not moved if a file with the same name already exists in the destination folder. Any skipped files are reported after the operation.
- The results refresh after a move so they always reflect the files currently on disk.

### Light and Dark appearance

Use the sun/moon button in the top-right corner to switch themes:

- ☀ Light — a bright, high-contrast workspace with clearly visible checkbox borders.
- ☾ Dark — a low-glare dark interface with readable table content and controls.

## Remembered preferences

The app uses native Qt settings on macOS to restore your last-used preferences when it opens:

- Selected folder path, if it still exists
- Similarity percentage
- Include Sub Folders setting
- Window width and height
- Width of every result-table column
- Light or Dark appearance

The restored folder is selected automatically, but the app does not rescan it until you click **Search Files**.

## Requirements

- macOS
- Python 3.10 or newer
- PyQt6
- Send2Trash

All Python dependencies are listed in [\`requirements.txt\`](requirements.txt).

## Installation

Clone or download this repository, then run the following commands from the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run

With the virtual environment active:

```bash
python Simility.py
```

The application includes a macOS launch workaround that locates PyQt's bundled Cocoa platform plugin automatically. If you launch it from an IDE, configure that IDE to use the project's `.venv` interpreter.

## macOS installer

A ready-to-open installer is available at [`dist/Simility.dmg`](dist/Simility.dmg).

1. Double-click `Simility.dmg` in Finder.
2. Drag **Simility.app** onto the **Applications** shortcut inside the installer window.
3. Open Simility from your Applications folder.

The standalone app bundle is also available at [`dist/Simility.app`](dist/Simility.app).

To rebuild both the `.app` and `.dmg` after changing the source code:

```bash
python -m pip install pyinstaller
bash build_macos_app.sh
```

The build creates an Apple Silicon (`arm64`) bundle, applies an ad-hoc local signature, and packages the bundle in a Finder-ready DMG. It is suitable for use on your own Mac; distributing it to other Macs may require Apple Developer signing and notarization.

## Project structure

```
.
├── Simility.py              # Application source code
├── build_macos_app.sh        # Rebuilds the macOS .app bundle
├── dist/Simility.app         # Ready-to-open macOS application
├── dist/Simility.dmg         # Drag-and-drop macOS installer
├── requirements.txt         # Python dependencies
└── README.md                # Project documentation
```

## Important notes

- Similar filename detection is a review aid; it does not prove that files have identical contents.
- Always inspect the selected files before moving them.
- Moving to Trash is recoverable until the Trash is emptied.
- Moving to another folder can be undone manually by moving files back from that destination.

## License

Add the license appropriate for your project before publishing.
