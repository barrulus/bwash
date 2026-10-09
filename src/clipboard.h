#pragma once

#include <gio/gio.h>

/* wl-copy's parent exits after handing the selection to its background
 * process. The helper takes ownership of a copy of bytes before completion. */
void swash_clipboard_copy_async(const char          *program,
                                GBytes              *bytes,
                                const char          *mime_type,
                                GAsyncReadyCallback  callback,
                                gpointer             user_data);
gboolean swash_clipboard_copy_finish(GAsyncResult *result, GError **error);
