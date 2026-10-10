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

Tesseract is optional and enables OCR support. On Wayland, install
`wl-clipboard` to let copied images outlive the editor process. The Nix package
already includes it.

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
available and does not change the supplied destination. Each editor keeps its
own destination. Without `--output-filename`, existing save behavior is unchanged.

### Independent captures

Each incoming image opens in a separate editor, including file arguments,
images piped to stdin, and files opened from the desktop. Each editor keeps
its own image, annotations, undo/redo history, and save destination. Opening a
second capture leaves the first available, including while it is saving.

“Open image” (Ctrl+O) also opens a separate editor when the current editor
already contains an image, preserving unsaved work. An empty editor can load
the selected file directly. Cancelling the chooser or selecting an invalid
image leaves existing documents unchanged.

Escape closes the current editor when “Escape closes window” is enabled.
Close after save and close after copy apply to that editor; Ctrl+Q quits all
editors. Launching Swash without an image presents an existing editor.

### Clipboard persistence

On Wayland, image copying hands PNG data to `wl-copy`, which keeps it available
after Swash exits, until the clipboard is replaced or cleared. No clipboard
history service is needed. Close after copy waits for this handoff to succeed;
if it fails, an error appears and the editor stays open so you can retry.
Closing or quitting during a copy also waits for its result.

If `wl-copy` is unavailable, Swash uses GTK and keeps an invisible process
alive while it owns the clipboard. This fallback has no expiry and releases
its ownership resources when the clipboard is replaced or cleared. OCR text
copying retains GTK's text formats and uses the same persistence on close.
Other display backends use GTK clipboard storage where available, with the
invisible process as a fallback.

## Tests

```bash
nix develop --command meson setup build --buildtype=debug
nix develop --command meson test -C build --print-errorlogs
```

The Nix development shell includes the GUI test dependencies. Outside Nix,
the `output-filename` test needs Python 3 with Pillow, `xdotool`, `xvfb-run`,
`gdbus`, and `dbus-run-session`; it reports a skip if these are unavailable. It uses
an isolated display, session bus, and temporary settings directory. It also
checks independent captures, undo/redo, file chooser behavior, and separate
exports with close after save.

The `clipboard-helper` test covers binary transfer, helper failure, and a
stalled handoff. The optional `clipboard-wayland` test uses a separate,
headless Umbriel session with no clipboard history service. It checks image
and OCR text pasting after close, failure recovery, and ownership release.
Set `BWASH_TEST_COMPOSITOR` to the Umbriel executable and `BWASH_TEST_INPUT`
to its built `tests/pointer-client` helper to enable it:

```bash
nix develop --command env \
  BWASH_TEST_COMPOSITOR=/path/to/umbriel \
  BWASH_TEST_INPUT=/path/to/umbriel/build-debug/tests/pointer-client \
  meson test -C build clipboard-wayland --print-errorlogs
```

For a real-time check beyond the former ten-minute expiry, also set
`BWASH_CLIPBOARD_SOAK_SECONDS=610` and pass `--timeout-multiplier 6` to Meson.
Repeat with `BWASH_CLIPBOARD_SOAK_FALLBACK=1` to exercise GTK retention without
the helper. These tests use synthetic images and their own clipboard.

## Acknowledgements

Swash is a fork of [Waytator](https://github.com/faetalize/waytator).

## License

Swash is licensed under the [GNU General Public License v3.0 or later](LICENSE).
