swash_conf = configuration_data()
swash_conf.set_quoted('SWASH_VERSION', meson.project_version())

swash_sources = files(
  'canvas-input.c',
  'canvas-layout.c',
  'canvas-render.c',
  'canvas-state.c',
  'clipboard.c',
  'clipboard.h',
  'document.c',
  'document.h',
  'editor-utils.c',
  'editor-utils.h',
  'export.c',
  'export.h',
  'ocr.c',
  'ocr.h',
  'render.c',
  'render.h',
  'stroke.c',
  'stroke.h',
  'types.h',
  'window.c',
  'window.h',
  'window-private.h',
)

configure_file(
  input: 'swash-config.h.in',
  output: 'swash-config.h',
  configuration: swash_conf,
)

swash_executable = executable(
  'swash',
  'main.c',
  swash_sources,
  swash_resources,
  dependencies: [gtk_dep, adw_dep, m_dep],
  install: true,
)

editor_utils_test = executable(
  'test-editor-utils',
  files(
    'test-editor-utils.c',
    'editor-utils.c',
    'stroke.c',
  ),
  dependencies: [gtk_dep, adw_dep, m_dep],
)

test('editor-utils', editor_utils_test)

clipboard_test = executable('test-clipboard',
  ['test-clipboard.c', 'clipboard.c'],
  dependencies: [gtk_dep],
)
test('clipboard-helper', clipboard_test, timeout: 30)

clipboard_ocr_test = executable('test-clipboard-ocr',
  'test-clipboard-ocr.c', swash_sources, swash_resources,
  dependencies: [gtk_dep, adw_dep, m_dep],
)

python = find_program('python3', required: false)
if python.found()
  open_dialog_test = executable('test-open-dialog',
    'test-open-dialog.c', swash_sources, swash_resources,
    dependencies: [gtk_dep, adw_dep, m_dep],
    c_args: ['-Wno-deprecated-declarations'],
  )
  finish_test = executable('test-finish',
    'test-finish.c', swash_sources, swash_resources,
    dependencies: [gtk_dep, adw_dep, m_dep],
    c_args: ['-Wno-deprecated-declarations'],
  )
  test('output-filename', python,
    args: [files('test-output-filename.py'), swash_executable, open_dialog_test, finish_test],
    timeout: 120,
    # xvfb-run's automatic display selection races between concurrent runs.
    is_parallel: false,
  )
  test('clipboard-wayland', python,
    args: [files('test-clipboard-wayland.py'), swash_executable, clipboard_ocr_test],
    timeout: 120,
  )
endif
