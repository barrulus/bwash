"""Exercise the real CLI, D-Bus forwarding, and Ctrl+S on an isolated display."""

import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def wait_for(predicate, description):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            print(f"PASS: {description}", flush=True)
            return result
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for {description}")


def run_tests(binary, chooser_binary, finish_binary, icons_binary, root):
    from PIL import Image

    config = root / "config" / "swash"
    config.mkdir(parents=True)
    settings = config / "settings.ini"
    settings.write_text("[preferences]\nshortcut_rotate=<Primary>r\n")
    os.environ.update(
        XDG_CONFIG_HOME=str(root / "config"),
        XDG_CACHE_HOME=str(root / "cache"),
        XDG_DATA_HOME=str(root / "data"),
        GDK_BACKEND="x11",
        GSK_RENDERER="cairo",
        GTK_A11Y="none",
        GTK_USE_PORTAL="0",
        GSETTINGS_BACKEND="memory",
        GIO_USE_VFS="local",
        GIO_USE_VOLUME_MONITOR="unix",
    )
    image = Image.new("RGB", (64, 48), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    png = buffer.getvalue()
    caller = root / "caller directory"
    caller.mkdir()
    source = caller / "original image.png"
    source.write_bytes(png)

    def xdo(*args, check=True):
        return subprocess.run(
            ["xdotool", *map(str, args)], capture_output=True, text=True,
            check=check, timeout=10,
        ).stdout.strip()

    def windows(process):
        return xdo("search", "--onlyvisible", "--pid", process.pid,
                   check=False).splitlines()

    def key(window, keys):
        xdo("windowfocus", "--sync", window)
        xdo("key", "--clearmodifiers", keys)

    def saved(path, size):
        try:
            with Image.open(path) as result:
                result.load()
                return result.size == size
        except (FileNotFoundError, OSError, SyntaxError):
            # A background export may still be writing the PNG chunks.
            return False

    def launch(*args, data=None):
        process = subprocess.Popen(
            [binary, *map(str, args)], cwd=root,
            stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
        )
        if data is not None:
            process.stdin.write(data)
            process.stdin.close()
        return process

    def remote(*args, data=None, success=True):
        result = subprocess.run(
            [binary, *map(str, args)], cwd=caller, input=data,
            capture_output=True, timeout=10,
        )
        assert (result.returncode == 0) == success, result.stderr.decode()
        return result

    def remote_window(process, *args, data=None):
        existing = set(windows(process))
        remote(*args, data=data)
        opened = wait_for(lambda: set(windows(process)) - existing, "independent editor")
        assert len(opened) == 1
        assert existing <= set(windows(process))
        return opened.pop()

    def stop(process):
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=10)

    # Closing an unsaved stdin capture must not create its destination.
    abandoned = root / "abandoned.png"
    process = launch("--stdin", "--output-filename", abandoned, data=png)
    try:
        window = wait_for(lambda: windows(process), "first window")[0]
        assert not abandoned.exists()
        key(window, "ctrl+q")
        assert process.wait(timeout=10) == 0
        assert not abandoned.exists()
    finally:
        stop(process)

    # A fresh launch resolves a relative destination without writing it yet.
    output = root / "first output.png"
    process = launch("--stdin", "--name", "capture.png",
                     "--output-filename", output.name, data=png)
    try:
        window = wait_for(lambda: windows(process), "editor window")[0]
        assert not output.exists()
        key(window, "ctrl+s")
        wait_for(lambda: saved(output, (64, 48)), "initial save")
        with Image.open(output) as result:
            assert result.convert("RGB").tobytes() == image.tobytes()

        # Rotate and annotate, then overwrite the same destination.
        key(window, "ctrl+r")
        key(window, "b")
        geometry = dict(line.split("=", 1) for line in
                        xdo("getwindowgeometry", "--shell", window).splitlines())
        x = int(geometry["WIDTH"]) // 2
        y = int(geometry["HEIGHT"]) // 2
        xdo("mousemove", "--window", window, x, y,
            "mousedown", 1, "mousemove", "--window", window, x + 30, y + 20,
            "mouseup", 1)
        # Save feedback temporarily disables the shortcut after an export.
        time.sleep(1.6)
        key(window, "ctrl+s")
        wait_for(lambda: saved(output, (48, 64)), "edited overwrite")
        with Image.open(output) as result:
            assert result.convert("RGB").tobytes() != image.tobytes()

        # A second invocation must use its own cwd, not the server's cwd.
        original_window = window
        annotated = output.read_bytes()
        window = remote_window(process, "--stdin", "--name", "remote.png", "--output-filename",
                               "remote output.png", data=png)
        remote_output = caller / "remote output.png"
        assert not remote_output.exists()
        time.sleep(1.6)
        key(window, "ctrl+s")
        wait_for(lambda: saved(remote_output, (64, 48)), "remote stdin save")
        assert not (root / "remote output.png").exists()

        # The first capture keeps its own edits, history and destination.
        assert output.read_bytes() == annotated
        key(original_window, "ctrl+z")  # Undo only the annotation.
        key(original_window, "ctrl+s")
        wait_for(lambda: saved(output, (48, 64)) and output.read_bytes() != annotated,
                 "first capture undo and save after second capture")
        with Image.open(output) as result:
            assert result.convert("RGB").tobytes() == image.tobytes()
        assert saved(remote_output, (64, 48))
        key(original_window, "ctrl+shift+z")
        time.sleep(1.6)
        key(original_window, "ctrl+s")
        wait_for(lambda: output.read_bytes() == annotated, "first capture redo retained")
        key(window, "ctrl+z")  # A fresh capture has no undo history.
        key(window, "ctrl+s")
        assert saved(remote_output, (64, 48))

        # File input and output stay separate, including repeated saves.
        window = remote_window(process, source.name, "--output-filename", "edited file.png")
        edited = caller / "edited file.png"
        time.sleep(1.6)
        key(window, "ctrl+r")
        key(window, "ctrl+s")
        wait_for(lambda: saved(edited, (48, 64)), "file input export")
        assert source.read_bytes() == png

        # Opening without the option gets an independent destination and
        # preserves ordinary in-place saves for file input.
        previous_output = edited.read_bytes()
        window = remote_window(process, source.name)
        time.sleep(1.6)
        key(window, "ctrl+r")
        key(window, "ctrl+s")
        wait_for(lambda: saved(source, (48, 64)), "ordinary file save")
        assert edited.read_bytes() == previous_output

        # Stdin without a destination still asks where to save. Cancelling
        # the dialog keeps the document open and creates no image.
        window = remote_window(process, "-", "--name", "dialog-only.png", data=png)
        time.sleep(1.6)
        editors = set(windows(process))
        key(window, "ctrl+s")
        dialogs = wait_for(lambda: [w for w in windows(process)
                                    if w != window and xdo("getwindowname", w) == "Save image"],
                           "ordinary save dialog")
        key(dialogs[-1], "Escape")
        wait_for(lambda: set(windows(process)) == editors, "cancelled save dialog")
        assert process.poll() is None
        assert not (root / "dialog-only.png").exists()
        assert not (caller / "dialog-only.png").exists()
        assert edited.read_bytes() == previous_output

        # Reject ambiguous or empty destinations without changing the document.
        rejected = remote("--output-filename", "unused.png", success=False)
        assert b"--output-filename requires" in rejected.stderr, (rejected.stderr.decode(), process.poll())
        rejected = remote(source.name, "--output-filename=", success=False)
        assert b"--output-filename requires" in rejected.stderr, (rejected.stderr.decode(), process.poll())
        assert not (caller / "unused.png").exists()

        # Invalid input must neither replace a document nor leak an empty window.
        remote("--stdin", data=b"not an image", success=False)
        remote("missing-image.png", success=False)
        assert set(windows(process)) == editors
        assert output.read_bytes() == annotated

        # Ctrl+O from an edited document opens separately. Cancelling Open
        # changes nothing.
        key(original_window, "ctrl+o")
        dialog = wait_for(lambda: [w for w in windows(process)
                                  if xdo("getwindowname", w) == "Open image"], "open dialog")[0]
        key(dialog, "Escape")
        wait_for(lambda: set(windows(process)) == editors, "cancelled open dialog")
        key(original_window, "ctrl+r")  # Leave unsaved work in the first editor.

        # Desktop Open requests can contain several files; none may be dropped.
        subprocess.run([
            "gdbus", "call", "--session", "--dest", "dev.lemmy.swash",
            "--object-path", "/dev/lemmy/swash", "--method", "org.gtk.Application.Open",
            "['" + source.as_uri() + "', '" + output.as_uri() + "']", "", "{}",
        ], check=True, capture_output=True, timeout=10)
        wait_for(lambda: len(set(windows(process)) - editors) == 2,
                 "desktop request opened both files")
        assert editors <= set(windows(process))
        key(original_window, "ctrl+s")
        wait_for(lambda: saved(output, (64, 48)), "unsaved original survived Open")
        remote()  # Launching with no image only presents an existing editor.
        assert len(set(windows(process)) - editors) == 2

        key(window, "ctrl+q")
        assert process.wait(timeout=10) == 0
    finally:
        stop(process)

    # Exercise the actual native chooser callback, including empty-window reuse.
    subprocess.run([chooser_binary, str(source)], check=True, timeout=15)

    # Start two exports in different editors. A slow PNG gives the first worker
    # time to overlap another capture; close-after-save must close only its own
    # window, and later errors must stay attached to the second document.
    settings.write_text("[preferences]\nclose_after_save=true\n")
    large_image = Image.effect_noise((3072, 2048), 100).convert("RGB")
    large_stream = io.BytesIO()
    large_image.save(large_stream, format="PNG")
    first_export = root / "large-export.png"
    second_export = root / "pending-parent" / "second-export.png"
    process = launch("--stdin", "--output-filename", first_export, data=large_stream.getvalue())
    try:
        first = wait_for(lambda: windows(process), "large capture editor")[0]
        # Open the second capture before exporting so the application stays
        # alive even on machines where the first export completes immediately.
        second = remote_window(process, "--stdin", "--output-filename", second_export, data=png)
        key(first, "ctrl+s")
        remote("--stdin", "--name", "during-export.png", data=png)
        third = wait_for(lambda: [w for w in windows(process) if w not in (first, second)],
                         "capture received during export")[0]
        key(third, "Escape")
        key(second, "ctrl+s")
        wait_for(lambda: saved(first_export, large_image.size), "first independent export")
        wait_for(lambda: first not in windows(process), "first editor closed after save")
        assert second in windows(process)
        assert not second_export.exists()
        with Image.open(first_export) as result:
            assert result.convert("RGB").tobytes() == large_image.tobytes()
        errors = wait_for(lambda: [w for w in windows(process) if w != second],
                          "second export error retained")
        key(errors[-1], "Escape")
        wait_for(lambda: windows(process) == [second], "second editor retained")
        second_export.parent.mkdir()
        key(second, "ctrl+s")
        assert process.wait(timeout=10) == 0
        assert saved(second_export, image.size)
    finally:
        stop(process)

    # Even with close-after-save enabled, failed saves must show an error
    # and retain a usable editor. Repair each path and retry the same save.
    for kind in ("missing parent", "unwritable parent"):
        settings.write_text("[preferences]\nclose_after_save=true\n")
        failed = root / kind / "output.png"
        if kind == "unwritable parent":
            failed.parent.mkdir(mode=0o500)
        process = launch("--stdin", "--output-filename", failed, data=png)
        try:
            window = wait_for(lambda: windows(process), "failure-test window")[0]
            key(window, "ctrl+s")
            dialogs = wait_for(lambda: [w for w in windows(process) if w != window],
                               "visible save error")
            assert process.poll() is None
            assert not failed.exists()
            key(dialogs[-1], "Escape")
            wait_for(lambda: len(windows(process)) == 1, "dismissed error")
            failed.parent.mkdir(exist_ok=True)
            failed.parent.chmod(0o700)
            key(window, "ctrl+s")
            assert process.wait(timeout=10) == 0
            assert saved(failed, (64, 48))
        finally:
            stop(process)
            if failed.parent.exists():
                failed.parent.chmod(0o700)

    settings.write_text("[preferences]\n")
    source.write_bytes(png)
    subprocess.run([icons_binary, str(source)], check=True, timeout=15)
    assert "selected_icon=heart" in settings.read_text()
    icon_output = root / "icons.png"
    process = launch("--stdin", "--output-filename", icon_output, data=png)
    try:
        window = wait_for(lambda: windows(process), "icon editor")[0]
        key(window, "i")
        geometry = dict(line.split("=", 1) for line in
                        xdo("getwindowgeometry", "--shell", window).splitlines())
        x = int(geometry["WIDTH"]) // 2
        y = int(geometry["HEIGHT"]) // 2
        xdo("mousemove", "--window", window, x, y, "click", 1)
        key(window, "ctrl+s")
        wait_for(lambda: saved(icon_output, (64, 48)), "placed icon export")
        with Image.open(icon_output) as result:
            pixels = result.convert("RGB")
            assert pixels.getpixel((32, 24)) == (0, 255, 0)
            assert pixels.getpixel((32, 14)) == (255, 255, 255)
            assert pixels.getpixel((22, 24)) == (255, 255, 255)
        original_icon = icon_output.read_bytes()

        def export_changed(previous, description):
            time.sleep(1.6)  # Save feedback temporarily disables save.
            key(window, "ctrl+s")
            wait_for(lambda: saved(icon_output, (64, 48))
                     and icon_output.read_bytes() != previous, description)
            return icon_output.read_bytes()

        key(window, "ctrl+z")
        blank = export_changed(original_icon, "icon undo")
        with Image.open(icon_output) as result:
            assert result.convert("RGB").tobytes() == image.tobytes()
        key(window, "ctrl+shift+z")
        assert export_changed(blank, "icon redo") == original_icon

        key(window, "m")
        xdo("mousemove", "--window", window, x, y, "mousedown", 1,
            "mousemove", "--window", window, x + 16, y, "mouseup", 1)
        moved = export_changed(original_icon, "moved icon export")
        with Image.open(icon_output) as result:
            pixels = result.convert("RGB")
            assert pixels.getpixel((32, 24)) == (255, 255, 255)
            assert pixels.getpixel((48, 24)) == (0, 255, 0)
        key(window, "e")
        xdo("mousemove", "--window", window, x + 16, y, "click", 1)
        assert export_changed(moved, "erased icon export") == blank
        key(window, "ctrl+z")
        assert export_changed(blank, "undo icon erasure") == moved
        key(window, "ctrl+q")
        assert process.wait(timeout=10) == 0
    finally:
        stop(process)

    settings.write_text("[preferences]\nshortcut_finish=Return\nclose_after_copy=true\nclose_after_save=true\n")
    subprocess.run([finish_binary, str(source), str(root / "finish.png")], check=True, timeout=15)

    print("PASS: direct saves, edited pixels, overwrite, cancellation, caller cwd,")
    print("      independent documents/history/exports, file chooser, CLI errors, save failure/retry")


if __name__ == "__main__":
    if "--inside" not in sys.argv:
        missing = [tool for tool in ("dbus-run-session", "xvfb-run", "xdotool", "gdbus")
                   if shutil.which(tool) is None]
        try:
            import PIL  # noqa: F401
        except ImportError:
            missing.append("Python Pillow")
        if missing:
            print("SKIP: GUI test requires " + ", ".join(missing))
            sys.exit(77)
        # Let xvfb-run supply a font configuration matching its own libraries.
        os.environ.pop("FONTCONFIG_FILE", None)
        os.environ.pop("FONTCONFIG_PATH", None)
        # Session services can outlive the runner briefly. A file-backed log
        # prevents inherited stdout pipes from holding Meson's test open.
        with tempfile.TemporaryDirectory(prefix="bwash-test-session-") as session, \
                tempfile.TemporaryFile(mode="w+") as log:
            # No service directories: the host's portal must not provide a
            # chooser on the real desktop or launch persistent session daemons.
            bus_config = Path(session) / "bus.conf"
            bus_config.write_text('''<busconfig>
              <type>session</type><listen>unix:tmpdir=/tmp</listen>
              <policy context="default">
                <allow own="*"/><allow send_destination="*"/>
                <allow receive_sender="*"/>
              </policy>
            </busconfig>''')
            result = subprocess.run([
                "dbus-run-session", f"--config-file={bus_config}", "--",
                "xvfb-run", "-a", "-s",
                "-screen 0 1280x1024x24", sys.executable,
                __file__, "--inside", str(Path(sys.argv[1]).resolve()),
                str(Path(sys.argv[2]).resolve()),
                str(Path(sys.argv[3]).resolve()),
                str(Path(sys.argv[4]).resolve()),
            ], stdout=log, stderr=subprocess.STDOUT, timeout=90)
            log.seek(0)
            print(log.read(), end="", flush=True)
        sys.exit(result.returncode)

    with tempfile.TemporaryDirectory(prefix="bwash-output-test-") as directory:
        run_tests(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], Path(directory))
