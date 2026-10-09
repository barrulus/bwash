#include "clipboard.h"

typedef struct {
  GSubprocess *process;
  guint timeout_id;
  gboolean timed_out;
} SwashClipboardTransfer;

static void
swash_clipboard_transfer_free(SwashClipboardTransfer *transfer)
{
  g_clear_handle_id(&transfer->timeout_id, g_source_remove);
  g_clear_object(&transfer->process);
  g_free(transfer);
}

static gboolean
swash_clipboard_transfer_timeout(gpointer user_data)
{
  SwashClipboardTransfer *transfer = user_data;

  transfer->timeout_id = 0;
  transfer->timed_out = TRUE;
  g_subprocess_force_exit(transfer->process);
  return G_SOURCE_REMOVE;
}

static void
swash_clipboard_helper_ready(GObject      *source,
                             GAsyncResult *result,
                             gpointer      user_data)
{
  g_autoptr(GTask) task = G_TASK(user_data);
  g_autoptr(GError) error = NULL;
  GSubprocess *process = G_SUBPROCESS(source);
  SwashClipboardTransfer *transfer = g_task_get_task_data(task);

  g_clear_handle_id(&transfer->timeout_id, g_source_remove);

  if (!g_subprocess_communicate_finish(process, result, NULL, NULL, &error)
      || !g_subprocess_get_successful(process)) {
    if (transfer->timed_out) {
      g_clear_error(&error);
      g_set_error_literal(&error, G_IO_ERROR, G_IO_ERROR_TIMED_OUT,
                          "Timed out handing the image to wl-copy; the editor is still open");
    } else if (error == NULL) {
      g_set_error_literal(&error, G_IO_ERROR, G_IO_ERROR_FAILED,
                          "wl-copy could not take ownership of the clipboard");
    }
    g_task_return_error(task, g_steal_pointer(&error));
    return;
  }

  g_task_return_boolean(task, TRUE);
}

void
swash_clipboard_copy_async(const char          *program,
                           GBytes              *bytes,
                           const char          *mime_type,
                           GAsyncReadyCallback  callback,
                           gpointer             user_data)
{
  g_autoptr(GTask) task = g_task_new(NULL, NULL, callback, user_data);
  g_autoptr(GError) error = NULL;
  g_autoptr(GSubprocess) process = NULL;
  SwashClipboardTransfer *transfer;

  /* Do not pipe stderr: wl-copy's background child inherits it and would
   * prevent communicate_finish from completing until the next selection.
   * No shell, command-line image bytes, or temporary image file is needed. */
  process = g_subprocess_new(G_SUBPROCESS_FLAGS_STDIN_PIPE
                              | G_SUBPROCESS_FLAGS_STDOUT_SILENCE
                              | G_SUBPROCESS_FLAGS_STDERR_SILENCE,
                            &error, program, "--type", mime_type, NULL);
  if (process == NULL) {
    g_task_return_error(task, g_steal_pointer(&error));
    return;
  }

  transfer = g_new0(SwashClipboardTransfer, 1);
  transfer->process = g_object_ref(process);
  /* Bound only the handoff, never the lifetime of the copied selection. */
  transfer->timeout_id = g_timeout_add_seconds(10, swash_clipboard_transfer_timeout, transfer);
  g_task_set_task_data(task, transfer, (GDestroyNotify) swash_clipboard_transfer_free);
  g_subprocess_communicate_async(process, bytes, NULL,
                                 swash_clipboard_helper_ready,
                                 g_steal_pointer(&task));
}

gboolean
swash_clipboard_copy_finish(GAsyncResult *result,
                            GError      **error)
{
  return g_task_propagate_boolean(G_TASK(result), error);
}
