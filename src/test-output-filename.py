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


def run_tests(binary, root):
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
        except (FileNotFoundError, OSError):
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
        remote("--stdin", "--name", "remote.png", "--output-filename",
               "remote output.png", data=png)
        remote_output = caller / "remote output.png"
        assert not remote_output.exists()
        time.sleep(1.6)
        key(window, "ctrl+s")
        wait_for(lambda: saved(remote_output, (64, 48)), "remote stdin save")
        assert not (root / "remote output.png").exists()

        # File input and output stay separate, including repeated saves.
        remote(source.name, "--output-filename", "edited file.png")
        edited = caller / "edited file.png"
        time.sleep(1.6)
        key(window, "ctrl+r")
        key(window, "ctrl+s")
        wait_for(lambda: saved(edited, (48, 64)), "file input export")
        assert source.read_bytes() == png

        # Opening without the option clears the previous destination and
        # preserves ordinary in-place saves for file input.
        previous_output = edited.read_bytes()
        remote(source.name)
        time.sleep(1.6)
        key(window, "ctrl+r")
        key(window, "ctrl+s")
        wait_for(lambda: saved(source, (48, 64)), "ordinary file save")
        assert edited.read_bytes() == previous_output

        # Stdin without a destination still asks where to save. Cancelling
        # the dialog keeps the document open and creates no image.
        remote("-", "--name", "dialog-only.png", data=png)
        time.sleep(1.6)
        key(window, "ctrl+s")
        dialogs = wait_for(lambda: [w for w in windows(process) if w != window],
                           "ordinary save dialog")
        key(dialogs[-1], "Escape")
        wait_for(lambda: len(windows(process)) == 1, "cancelled save dialog")
        assert process.poll() is None
        assert not (root / "dialog-only.png").exists()
        assert not (caller / "dialog-only.png").exists()
        assert edited.read_bytes() == previous_output

        # Reject ambiguous or empty destinations without changing the document.
        assert b"--output-filename requires" in remote(
            "--output-filename", "unused.png", success=False).stderr
        assert b"--output-filename requires" in remote(
            source.name, "--output-filename=", success=False).stderr
        assert not (caller / "unused.png").exists()
        key(window, "ctrl+q")
        assert process.wait(timeout=10) == 0
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

    print("PASS: direct saves, edited pixels, overwrite, cancellation, caller cwd,")
    print("      source preservation, destination reset, CLI errors, save failure/retry")


if __name__ == "__main__":
    if "--inside" not in sys.argv:
        missing = [tool for tool in ("dbus-run-session", "xvfb-run", "xdotool")
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
            ], stdout=log, stderr=subprocess.STDOUT, timeout=90)
            log.seek(0)
            print(log.read(), end="", flush=True)
        sys.exit(result.returncode)

    with tempfile.TemporaryDirectory(prefix="bwash-output-test-") as directory:
        run_tests(sys.argv[2], Path(directory))
