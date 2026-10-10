"""Clipboard checks on an isolated, history-free headless Umbriel session.

Set BWASH_TEST_COMPOSITOR and BWASH_TEST_INPUT to Umbriel and its pointer-client
test helper. BWASH_CLIPBOARD_SOAK_SECONDS optionally extends the final check.
"""

import io
import json
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


def check(binary, ocr_binary, root):
    from PIL import Image

    compositor = os.environ["BWASH_TEST_COMPOSITOR"]
    pointer = os.environ["BWASH_TEST_INPUT"]
    runtime = root / "runtime"
    runtime.mkdir(mode=0o700)
    config = root / "config" / "swash"
    config.mkdir(parents=True)
    settings = config / "settings.ini"
    settings.write_text("[preferences]\nclose_after_copy=true\n")
    os.environ.update(
        XDG_RUNTIME_DIR=str(runtime), XDG_CONFIG_HOME=str(root / "config"),
        XDG_CACHE_HOME=str(root / "cache"), XDG_DATA_HOME=str(root / "data"),
        GDK_BACKEND="wayland", GSK_RENDERER="cairo", GTK_A11Y="none",
        GSETTINGS_BACKEND="memory", GIO_USE_VFS="local",
        GIO_USE_VOLUME_MONITOR="unix", WLR_BACKENDS="headless",
        WLR_LIBINPUT_NO_DEVICES="1", WLR_HEADLESS_OUTPUTS="1",
    )
    os.environ.pop("DISPLAY", None)
    os.environ.pop("WAYLAND_DISPLAY", None)
    os.environ.pop("UMBRIEL_SOCKET", None)
    compositor_config = root / "compositor.toml"
    compositor_config.write_text(
        "[general]\nxwayland=false\nshow_cheatsheet=false\nautostart=[]\n"
    )
    processes = []

    def spawn(args, **kwargs):
        process = subprocess.Popen(args, **kwargs)
        processes.append(process)
        return process

    def run(args, **kwargs):
        if Path(args[0]).name == "wl-copy":
            # The background owner inherits stderr; do not wait for its EOF.
            return subprocess.run(args, check=True, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, timeout=10, **kwargs)
        return subprocess.run(args, check=True, capture_output=True, timeout=10, **kwargs)

    def windows():
        return json.loads(run([compositor, "windows", "--json"]).stdout)

    def key(code, modifier="none"):
        run([pointer, "1280", "720", "keyboard-only", "mod", modifier,
             "tap", str(code), "mod", "none"])

    image = Image.new("RGB", (64, 48), (17, 83, 149))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    png = stream.getvalue()

    def paste_image(expected=None):
        expected = image if expected is None else expected
        result = subprocess.run(["wl-paste", "--no-newline", "--type", "image/png"],
                                capture_output=True, timeout=10)
        if result.returncode:
            return False
        with Image.open(io.BytesIO(result.stdout)) as pasted:
            return pasted.size == expected.size and pasted.convert("RGB").tobytes() == expected.tobytes()

    def clear():
        run(["wl-copy", "--clear"])

    def launch(env=None, output=None):
        args = [binary, "--stdin", "--name", "clipboard.png"]
        if output is not None:
            args += ["--output-filename", str(output)]
        process = spawn(args,
                        stdin=subprocess.PIPE, env=env)
        process.stdin.write(png)
        process.stdin.close()
        wait_for(lambda: any(w.get("focused") for w in windows()), "focused editor")
        return process

    log = (root / "compositor.log").open("w+")
    try:
        server = spawn([compositor, "-c", str(compositor_config)],
                       stdout=log, stderr=subprocess.STDOUT)
        wait_for(lambda: (runtime / "wayland-0").exists() or server.poll() is not None,
                 "headless compositor startup")
        if server.poll() is not None:
            log.seek(0)
            raise AssertionError(log.read())
        os.environ["WAYLAND_DISPLAY"] = "wayland-0"
        os.environ["UMBRIEL_SOCKET"] = str(runtime / "umbriel-wayland-0.sock")
        # Keep keyboard capability present between input commands.
        keyboard = spawn([pointer, "1", "1", "keyboard-only", "mod", "none",
                          "mark", "ready", "hold"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        assert keyboard.stdout.readline().strip() == b"ready"

        # Successful handoff really exits the editor, and supports many pastes.
        process = launch()
        key(46, "control")  # Ctrl+C
        assert process.wait(timeout=10) == 0
        wait_for(lambda: not windows(), "close after helper handoff")
        assert paste_image() and paste_image()
        assert b"image/png" in run(["wl-paste", "--list-types"]).stdout
        print("PASS: image MIME type and repeated paste after editor exit", flush=True)
        clear()

        # Normal copy followed by Quit also survives.
        settings.write_text("[preferences]\nclose_after_copy=false\n")
        process = launch()
        key(46, "control")
        wait_for(paste_image, "ordinary image copy")
        key(16, "control")  # Ctrl+Q
        assert process.wait(timeout=10) == 0
        assert paste_image()
        clear()

        # An installed but failing helper must not close the editor or destroy
        # the previous clipboard. Test Quit while a handoff is pending too.
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        fake = fake_bin / "wl-copy"
        shell = shutil.which("sh")
        started = root / "helper-started"
        # A separate failure script consumes input, waits, and exits nonzero.
        fake.write_text(f"#!{shell}\n: > {started}\n{shutil.which('cat')} >/dev/null\n"
                        f"{shutil.which('sleep')} 1\nexit 1\n")
        fake.chmod(0o700)
        failure_env = dict(os.environ, PATH=f"{fake_bin}:{os.environ['PATH']}")
        settings.write_text("[preferences]\nclose_after_copy=true\n")
        run(["wl-copy", "--type", "text/plain;charset=utf-8"], input=b"previous clipboard")
        process = launch(failure_env)
        key(46, "control")
        wait_for(started.exists, "helper transfer started")
        key(16, "control")
        wait_for(lambda: len(windows()) >= 2, "visible helper error after pending Quit")
        assert process.poll() is None
        assert run(["wl-paste", "--no-newline"]).stdout == b"previous clipboard"
        key(1)  # Escape dismisses the alert.
        wait_for(lambda: len(windows()) == 1, "editor retained after failure")
        fake.unlink()
        key(46, "control")  # Resolve the real helper and retry.
        assert process.wait(timeout=10) == 0
        assert paste_image()
        clear()

        # No helper in the editor's PATH: GTK retains ownership invisibly.
        # Closing a second window must reuse the hold rather than leak it.
        no_helper = dict(os.environ, PATH=str(fake_bin))
        for _ in range(2):
            process = launch(no_helper)
            key(46, "control")
            wait_for(lambda: not windows(), "GTK fallback window closed")
            assert paste_image()
            assert process.poll() is None or process.returncode == 0
        run(["wl-copy", "--type", "text/plain"], input=b"replacement")
        for candidate in processes:
            if candidate.args[0] == binary:
                assert candidate.wait(timeout=10) == 0
        print("PASS: missing-helper fallback and release after replacement", flush=True)
        clear()

        # OCR uses a real GtkTextView selection, preserving UTF-8 and newlines.
        process = spawn([ocr_binary])
        wait_for(lambda: any(w.get("focused") for w in windows()), "focused OCR editor")
        key(46, "control")

        def pasted_text():
            result = subprocess.run(["wl-paste", "--no-newline", "--type", "text/plain;charset=utf-8"],
                                    capture_output=True, timeout=10)
            return result.returncode == 0 and result.stdout == "OCR clipboard: café\nsecond line".encode()

        wait_for(pasted_text, "OCR text paste after close")
        wait_for(lambda: not windows(), "OCR editor closed")
        assert process.poll() is None
        clear()
        assert process.wait(timeout=10) == 0

        # Combined action must override early-close preferences without changing
        # ordinary copy/save behavior, and preserve the copied pixels on disk.
        finish_settings = ("[preferences]\nshortcut_finish=Return\n"
                           "close_after_copy=true\nclose_after_save=true\n")
        settings.write_text(finish_settings)
        output = root / "combined.png"
        process = launch(output=output)
        key(28)  # Enter, explicitly configured as Finish.
        assert process.wait(timeout=10) == 0
        assert paste_image()
        with Image.open(output) as saved:
            assert saved.size == image.size and saved.convert("RGB").tobytes() == image.tobytes()
        clear()
        print("PASS: combined copy, save, close with both close preferences enabled", flush=True)

        # With ordinary close preferences off, Finish still closes. The native
        # Wayland fallback must retain its input serial despite pausing edits.
        settings.write_text("[preferences]\nshortcut_finish=Return\n")
        output = root / "combined-native.png"
        process = launch(no_helper, output)
        key(28)
        wait_for(lambda: not windows(), "combined GTK fallback closed")
        assert output.exists() and paste_image() and process.poll() is None
        clear()
        assert process.wait(timeout=10) == 0
        settings.write_text(finish_settings)

        # Failed handoff must never begin saving. Retrying uses the same editor.
        fake.write_text(f"#!{shell}\n{shutil.which('cat')} >/dev/null\nexit 1\n")
        fake.chmod(0o700)
        output = root / "copy-failure.png"
        process = launch(failure_env, output)
        key(28)
        wait_for(lambda: len(windows()) >= 2, "combined copy error")
        assert process.poll() is None and not output.exists()
        key(1)
        wait_for(lambda: len(windows()) == 1, "combined editor usable after copy error")
        fake.unlink()
        key(28)
        assert process.wait(timeout=10) == 0
        assert output.exists() and paste_image()
        clear()

        # Save failure follows a successful copy and keeps the document open.
        output = root / "missing-parent" / "save-failure.png"
        process = launch(output=output)
        key(28)
        wait_for(lambda: len(windows()) >= 2, "combined save error")
        assert process.poll() is None and not output.exists() and paste_image()
        key(1)
        wait_for(lambda: len(windows()) == 1, "combined editor usable after save error")
        output.parent.mkdir()
        key(28)
        assert process.wait(timeout=10) == 0
        assert output.exists()
        clear()

        # Wait for an existing auto-copy, then copy the frozen latest document
        # before saving. A slow helper makes the overlap deterministic.
        real_helper = shutil.which("wl-copy")
        calls = root / "copy-calls"
        fake.write_text(f'#!{shell}\necho copy >> {calls}\n'
                        f'{shutil.which("sleep")} 0.5\nexec {real_helper} "$@"\n')
        fake.chmod(0o700)
        settings.write_text(finish_settings + "auto_copy_latest_change=true\nshortcut_rotate=<Primary>r\n")
        output = root / "auto-copy-finish.png"
        process = launch(failure_env, output)
        key(19, "control")  # Rotate, starting auto-copy.
        wait_for(calls.exists, "auto-copy started before Finish")
        key(28)
        assert not output.exists()
        assert process.wait(timeout=10) == 0
        assert len(calls.read_text().splitlines()) == 2
        rotated = image.transpose(Image.Transpose.ROTATE_90)
        assert paste_image(rotated)
        with Image.open(output) as saved:
            assert saved.size == rotated.size and saved.convert("RGB").tobytes() == rotated.tobytes()
        fake.unlink()
        clear()
        print("PASS: combined failures/retries and auto-copy ordering", flush=True)

        settings.write_text("[preferences]\nclose_after_copy=true\n")
        # Optional real-time check beyond the old ten-minute expiry.
        fallback_soak = os.environ.get("BWASH_CLIPBOARD_SOAK_FALLBACK") == "1"
        process = launch(no_helper if fallback_soak else None)
        key(46, "control")
        wait_for(lambda: not windows(), "soak editor closed")
        if fallback_soak:
            assert process.poll() is None
        else:
            assert process.wait(timeout=10) == 0
        assert paste_image()
        seconds = int(os.environ.get("BWASH_CLIPBOARD_SOAK_SECONDS", "0"))
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            time.sleep(min(30, deadline - time.monotonic()))
            assert paste_image()
            print(f"Clipboard still pasteable; {max(0, int(deadline - time.monotonic()))}s remaining", flush=True)
        clear()
        assert process.wait(timeout=10) == 0
        print(f"PASS: clipboard persistence ({seconds}s soak), with no history service", flush=True)
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        log.close()


if __name__ == "__main__":
    required = ("BWASH_TEST_COMPOSITOR", "BWASH_TEST_INPUT")
    if any(not os.environ.get(name) for name in required):
        print("SKIP: set BWASH_TEST_COMPOSITOR and BWASH_TEST_INPUT for Wayland tests")
        sys.exit(77)
    if "--inside" in sys.argv:
        with tempfile.TemporaryDirectory(prefix="bwc-", dir="/tmp") as root:
            check(sys.argv[2], sys.argv[3], Path(root))
    else:
        with tempfile.TemporaryDirectory(prefix="bwash-clipboard-bus-") as root:
            config = Path(root) / "bus.conf"
            config.write_text('''<busconfig>
              <type>session</type><listen>unix:tmpdir=/tmp</listen>
              <policy context="default"><allow own="*"/>
                <allow send_destination="*"/><allow receive_sender="*"/>
              </policy></busconfig>''')
            result = subprocess.run([
                "dbus-run-session", f"--config-file={config}", "--", sys.executable,
                __file__, "--inside", str(Path(sys.argv[1]).resolve()),
                str(Path(sys.argv[2]).resolve()),
            ])
            sys.exit(result.returncode)
