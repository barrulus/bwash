#define _POSIX_C_SOURCE 200809L
#include "clipboard.h"

#include <glib/gstdio.h>
#include <unistd.h>

#define PAYLOAD_SIZE (256 * 1024)

static char *helper_path;
static GAsyncResult *copy_result;

static void
copy_ready(GObject *source, GAsyncResult *result, gpointer data)
{
  (void) source;
  (void) data;
  copy_result = g_object_ref(result);
}

static gboolean
copy_with_helper(const char *program, const char *mime_type, GError **error)
{
  guchar *data = g_malloc(PAYLOAD_SIZE);
  g_autoptr(GBytes) bytes = NULL;
  gboolean success;

  for (gsize i = 0; i < PAYLOAD_SIZE; i++)
    data[i] = i % 251;
  bytes = g_bytes_new_take(data, PAYLOAD_SIZE);
  swash_clipboard_copy_async(program, bytes, mime_type, copy_ready, NULL);
  /* The asynchronous call must retain the binary payload itself. */
  g_clear_pointer(&bytes, g_bytes_unref);
  while (copy_result == NULL)
    g_main_context_iteration(NULL, TRUE);
  success = swash_clipboard_copy_finish(copy_result, error);
  g_clear_object(&copy_result);
  return success;
}

static void
test_binary_stream(void)
{
  g_autoptr(GError) error = NULL;
  gint64 started = g_get_monotonic_time();

  g_assert_true(copy_with_helper(helper_path, "image/png", &error));
  g_assert_no_error(error);
  g_assert_cmpint(g_get_monotonic_time() - started, <, 1500 * G_TIME_SPAN_MILLISECOND);
}

static void
test_failure(void)
{
  g_autoptr(GError) error = NULL;

  g_assert_false(copy_with_helper(helper_path, "application/x-failure", &error));
  g_assert_nonnull(error);
}

static void
test_missing_helper(void)
{
  g_autoptr(GError) error = NULL;

  g_assert_false(copy_with_helper("/nonexistent/bwash-wl-copy", "image/png", &error));
  g_assert_error(error, G_SPAWN_ERROR, G_SPAWN_ERROR_NOENT);
}

static void
test_handoff_timeout(void)
{
  g_autoptr(GError) error = NULL;

  g_assert_false(copy_with_helper(helper_path, "application/x-hang", &error));
  g_assert_error(error, G_IO_ERROR, G_IO_ERROR_TIMED_OUT);
}

static int
run_fake_helper(const char *mime_type)
{
  guchar buffer[4096];
  gsize offset = 0;
  ssize_t count;

  if (g_str_equal(mime_type, "application/x-failure"))
    return 1; /* Fail before reading, exercising broken-pipe handling too. */
  if (g_str_equal(mime_type, "application/x-hang")) {
    sleep(30);
    return 1;
  }
  if (!g_str_equal(mime_type, "image/png"))
    return 2;

  while ((count = read(STDIN_FILENO, buffer, sizeof(buffer))) > 0) {
    for (ssize_t i = 0; i < count; i++, offset++)
      if (buffer[i] != offset % 251)
        return 3;
  }
  if (count < 0 || offset != PAYLOAD_SIZE)
    return 4;

  /* Like wl-copy, leave a background child with inherited stderr. It must
   * not hold up the handoff completion callback. */
  pid_t child = fork();
  if (child < 0)
    return 5;
  if (child == 0) {
    sleep(2);
    _exit(0);
  }
  return 0;
}

int
main(int argc, char **argv)
{
  g_autoptr(GError) error = NULL;
  g_autofree char *directory = NULL;
  g_autofree char *executable = NULL;
  int result;

  if (argc == 3 && g_str_equal(argv[1], "--type"))
    return run_fake_helper(argv[2]);

  g_test_init(&argc, &argv, NULL);
  directory = g_dir_make_tmp("bwash-clipboard-helper-XXXXXX", &error);
  g_assert_no_error(error);
  helper_path = g_build_filename(directory, "helper with spaces ; $literal", NULL);
  executable = g_file_read_link("/proc/self/exe", &error);
  g_assert_no_error(error);
  g_assert_cmpint(symlink(executable, helper_path), ==, 0);

  g_test_add_func("/clipboard/binary-stream", test_binary_stream);
  g_test_add_func("/clipboard/helper-failure", test_failure);
  g_test_add_func("/clipboard/missing-helper", test_missing_helper);
  g_test_add_func("/clipboard/handoff-timeout", test_handoff_timeout);
  result = g_test_run();

  g_unlink(helper_path);
  g_rmdir(directory);
  g_free(helper_path);
  return result;
}
