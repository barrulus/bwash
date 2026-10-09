#pragma once

#include <adwaita.h>

G_BEGIN_DECLS

#define SWASH_TYPE_WINDOW (swash_window_get_type())

G_DECLARE_FINAL_TYPE(SwashWindow, swash_window, SWASH, WINDOW, AdwApplicationWindow)

SwashWindow *swash_window_new(AdwApplication *app);
gboolean swash_window_open_file(SwashWindow *self,
                                   GFile          *file,
                                   GError        **error);
gboolean swash_window_open_bytes(SwashWindow *self,
                                    GBytes         *bytes,
                                    const char     *display_name,
                                    GError        **error);

/* The explicit save destination is separate from the source and is cleared
 * when another image is opened. Setting it does not write a file. */
void swash_window_set_output_file(SwashWindow *self, GFile *file);

void swash_window_save_state(SwashWindow *self);

G_END_DECLS
