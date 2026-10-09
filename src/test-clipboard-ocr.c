/* Exercise GTK's actual OCR text view copy signal and the window close path
 * without depending on OCR recognition accuracy or screen coordinates. */
#include "window-private.h"

static gboolean
copy_text_on_key(GtkEventControllerKey *controller, guint keyval,
                 guint keycode, GdkModifierType state, gpointer data)
{
  SwashWindow *window = SWASH_WINDOW(data);
  GtkTextBuffer *buffer;
  GtkTextIter start, end;

  (void) controller;
  (void) keycode;

  if (keyval != GDK_KEY_c || !(state & GDK_CONTROL_MASK))
    return FALSE;
  buffer = gtk_text_view_get_buffer(window->ocr_all_text_view);
  gtk_text_buffer_set_text(buffer, "OCR clipboard: café\nsecond line", -1);
  gtk_text_buffer_get_bounds(buffer, &start, &end);
  gtk_text_buffer_select_range(buffer, &start, &end);
  g_signal_emit_by_name(window->ocr_all_text_view, "copy-clipboard");
  gtk_window_close(GTK_WINDOW(window));
  return TRUE;
}

static void
activate(GApplication *app, gpointer data)
{
  SwashWindow *window = swash_window_new(ADW_APPLICATION(app));
  GtkEventController *keys = gtk_event_controller_key_new();

  (void) data;
  gtk_event_controller_set_propagation_phase(keys, GTK_PHASE_CAPTURE);
  g_signal_connect(keys, "key-pressed", G_CALLBACK(copy_text_on_key), window);
  gtk_widget_add_controller(GTK_WIDGET(window), keys);
  gtk_window_present(GTK_WINDOW(window));
}

int
main(int argc, char **argv)
{
  g_autoptr(AdwApplication) app = adw_application_new("dev.lemmy.swash.ClipboardTest", 0);

  g_application_set_resource_base_path(G_APPLICATION(app), "/dev/lemmy/swash");
  g_signal_connect(app, "activate", G_CALLBACK(activate), NULL);
  return g_application_run(G_APPLICATION(app), argc, argv);
}
