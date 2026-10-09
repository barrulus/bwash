# Swash

Swash is a fast screenshot annotator and lightweight image editor for Linux,
built with GTK 4 and libadwaita.

<p align="center">
  <img width="1000" alt="Swash annotating the MDN CSS documentation" src="docs/images/swash-screenshot.png" />
</p>

## Features

- Freehand drawing, highlighting, text, arrows, shapes, and numbered markers
- Cropping, rotation, flipping, blurring, and annotation erasing
- Moveable annotations with configurable colors, fills, and sizes
- Undo and redo history
- OCR text recognition through Tesseract
- Copy to the clipboard or save to a file
- Open image files or read image data from standard input

## Installation

### Arch Linux

Install Swash from the AUR:

```bash
yay -S swash
```

### Build from source

Required dependencies:

- Meson
- Ninja
- pkg-config
- GTK 4
- libadwaita 1.6 or newer
- A C compiler such as GCC or Clang

Tesseract is optional and enables OCR support.

Configure, build, and install Swash into `/usr/local`:

```bash
meson setup build --buildtype=release
meson compile -C build
sudo meson install -C build
```

The application ID is `dev.lemmy.swash`.

## Usage

Launch Swash without an image:

```bash
swash
```

Show command-line options or the installed version:

```bash
swash --help
swash --version
```

Open an existing image:

```bash
swash path/to/image.png
```

Pipe image data directly into Swash:

```bash
grim -g "$(slurp)" - | swash
```

Use `--stdin` explicitly and set the suggested filename for saving:

```bash
grim -g "$(slurp)" - | swash --stdin --name "Screenshot.png"
```

Supply a destination to save with Ctrl+S without a file dialog:

```bash
grim -g "$(slurp)" - | swash --stdin --name "Screenshot.png" --output-filename "$HOME/Pictures/Screenshots/Screenshot.png"
swash original.png --output-filename "edited copy.png"
```

`--output-filename` requires an input image (a file, `-`, or `--stdin`).
Relative destinations are resolved against the invoking command's working
directory, including when Swash is already running. Opening or closing the
editor does not create the output file; it is written only when you save.
The parent directory must already exist. Invalid or unwritable destinations
show an error when saving and leave the editor open.

Saving replaces an existing destination without an overwrite prompt. The
input file is kept separate and is only overwritten if you explicitly choose
it as the destination. The filename extension selects the export format, as
with ordinary saves; unknown extensions use PNG. “Save as copy” remains
available and does not change the supplied destination. Opening another image
clears that destination. Without `--output-filename`, existing save behavior
is unchanged.

## Tests

```bash
nix develop --command meson setup build --buildtype=debug
nix develop --command meson test -C build --print-errorlogs
```

The Nix development shell includes the GUI test dependencies. Outside Nix,
the `output-filename` test needs Python 3 with Pillow, `xdotool`, `xvfb-run`,
and `dbus-run-session`; it reports a skip if these are unavailable. It uses
an isolated display, session bus, and temporary settings directory.

## Acknowledgements

Swash is a fork of [Waytator](https://github.com/faetalize/waytator).

## License

Swash is licensed under the [GNU General Public License v3.0 or later](LICENSE).
