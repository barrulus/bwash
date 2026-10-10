/* Native GTK checks for Finish cancellation, retry, and text/crop key priority.
 * The Python runner supplies an isolated X11 display, bus and settings. */
#include "window-private.h"

static SwashWindow *window;
static GBytes *input;
static GFile *output;
static GtkWindow *chooser;
static guint phase;
static gint64 chooser_ready_at;

static gboolean
enter(GtkWidget *widget)
{
  g_autoptr(GListModel) controllers = gtk_widget_observe_controllers(widget);
  for (guint i = 0; i < g_list_model_get_n_items(controllers); i++) {
    g_autoptr(GtkEventController) controller = g_list_model_get_item(controllers, i);
    gboolean handled = FALSE;
    if (GTK_IS_EVENT_CONTROLLER_KEY(controller)
        && g_signal_handler_find(controller, G_SIGNAL_MATCH_DATA, 0, 0, NULL, NULL, window) != 0) {
      g_signal_emit_by_name(controller, "key-pressed", GDK_KEY_Return, 0, 0, &handled);
      if (handled)
        return TRUE;
    }
  }
  return FALSE;
}

static GtkWindow *
find_chooser(void)
{
  GListModel *windows = gtk_window_get_toplevels();
  for (guint i = 0; i < g_list_model_get_n_items(windows); i++) {
    g_autoptr(GtkWindow) candidate = g_list_model_get_item(windows, i);
    if (GTK_IS_FILE_CHOOSER(candidate))
      return g_steal_pointer(&candidate);
  }
  return NULL;
}

static gboolean
advance(gpointer data)
{
  GApplication *app = data;
  GdkClipboard *clipboard = gdk_display_get_clipboard(gdk_display_get_default());

  if (phase == 0) {
    g_assert_cmpstr(window->shortcut_accels[SWASH_SHORTCUT_FINISH], ==, "Return");
    window->text_editing = TRUE;
    gtk_widget_set_visible(window->text_input_hidden, TRUE);
    gtk_widget_grab_focus(window->text_input_hidden);
    gtk_widget_activate_action(GTK_WIDGET(window), "win.finish", NULL);
    g_assert_false(window->finish_in_progress);
    g_assert_true(enter(window->text_input_hidden));
    g_assert_false(window->text_editing);
    g_assert_false(window->finish_in_progress);

    gtk_widget_grab_focus(GTK_WIDGET(window->drawing_area));
    window->active_tool = SWASH_TOOL_CROP;
    window->crop_selection_active = TRUE;
    window->crop_start_x = window->crop_start_y = 0;
    window->crop_end_x = 10;
    window->crop_end_y = 12;
    g_assert_true(enter(GTK_WIDGET(window)));
    g_assert_false(window->crop_selection_active);
    g_assert_false(window->finish_in_progress);
    g_assert_cmpint(gdk_texture_get_width(window->texture), ==, 10);
    g_assert_cmpint(gdk_texture_get_height(window->texture), ==, 12);
    g_assert_true(enter(GTK_WIDGET(window)));
    g_assert_true(window->finish_in_progress);
    phase = 1;
  } else if (phase == 1) {
    if (chooser == NULL) {
      chooser = find_chooser();
      chooser_ready_at = g_get_monotonic_time() + 500 * G_TIME_SPAN_MILLISECOND;
    }
    if (chooser == NULL)
      return G_SOURCE_CONTINUE;
    /* GTK's native chooser initializes its path bar asynchronously. Allow
     * it to settle before driving a response directly through its signal. */
    if (g_get_monotonic_time() < chooser_ready_at)
      return G_SOURCE_CONTINUE;
    g_assert_nonnull(gdk_clipboard_get_content(clipboard));
    g_assert_true(window->save_in_progress);
    g_assert_false(gtk_widget_get_sensitive(GTK_WIDGET(window)));
    gtk_window_close(GTK_WINDOW(window));
    g_assert_nonnull(gtk_window_get_application(GTK_WINDOW(window)));
    gtk_widget_activate_action(GTK_WIDGET(window), "win.finish", NULL);
    gtk_dialog_response(GTK_DIALOG(chooser), GTK_RESPONSE_CANCEL);
    g_clear_object(&chooser);
    phase = 2;
  } else if (phase == 2) {
    if (window->finish_in_progress)
      return G_SOURCE_CONTINUE;
    g_assert_false(window->save_in_progress);
    g_assert_true(gtk_widget_get_sensitive(GTK_WIDGET(window)));
    g_assert_nonnull(gtk_window_get_application(GTK_WINDOW(window)));
    g_assert_true(swash_document_has_unsaved_changes(window->document));
    g_assert_false(g_file_query_exists(output, NULL));
    gtk_widget_grab_focus(GTK_WIDGET(window->drawing_area));
    g_assert_true(enter(GTK_WIDGET(window)));
    phase = 3;
  } else if (phase == 3) {
    chooser = find_chooser();
    if (chooser == NULL)
      return G_SOURCE_CONTINUE;
    g_autoptr(GFile) parent = g_file_get_parent(output);
    g_autofree char *name = g_file_get_basename(output);
    g_assert_true(gtk_file_chooser_set_current_folder(GTK_FILE_CHOOSER(chooser), parent, NULL));
    gtk_file_chooser_set_current_name(GTK_FILE_CHOOSER(chooser), name);
    chooser_ready_at = g_get_monotonic_time() + 500 * G_TIME_SPAN_MILLISECOND;
    phase = 4;
  } else if (phase == 4) {
    g_autoptr(GFile) selected = gtk_file_chooser_get_file(GTK_FILE_CHOOSER(chooser));
    if (selected == NULL || !g_file_equal(selected, output)
        || g_get_monotonic_time() < chooser_ready_at)
      return G_SOURCE_CONTINUE;
    g_assert_true(window->finish_in_progress);
    g_assert_false(g_file_query_exists(output, NULL));
    gtk_dialog_response(GTK_DIALOG(chooser), GTK_RESPONSE_ACCEPT);
    g_clear_object(&chooser);
    phase = 5;
  } else {
    if (window != NULL)
      return G_SOURCE_CONTINUE;
    g_autoptr(GError) error = NULL;
    g_autoptr(GdkTexture) saved = gdk_texture_new_from_file(output, &error);
    g_assert_no_error(error);
    g_assert_cmpint(gdk_texture_get_width(saved), ==, 10);
    g_assert_cmpint(gdk_texture_get_height(saved), ==, 12);
    g_assert_nonnull(gdk_clipboard_get_content(clipboard));
    gdk_clipboard_set_content(clipboard, NULL);
    g_application_release(app);
    g_print("PASS: Finish text/crop priority, cancelled save, retry, native clipboard and close\n");
    return G_SOURCE_REMOVE;
  }
  return G_SOURCE_CONTINUE;
}

static void
activate(GApplication *app, gpointer data)
{
  (void) data;
  g_autoptr(GError) error = NULL;
  g_application_hold(app);
  window = swash_window_new(ADW_APPLICATION(app));
  g_object_add_weak_pointer(G_OBJECT(window), (gpointer *) &window);
  g_assert_true(swash_window_open_bytes(window, input, "finish.png", &error));
  g_assert_no_error(error);
  gtk_window_present(GTK_WINDOW(window));
  g_timeout_add(50, advance, app);
}

int
main(int argc, char **argv)
{
  g_assert_cmpint(argc, ==, 3);
  g_autoptr(GFile) source = g_file_new_for_path(argv[1]);
  input = g_file_load_bytes(source, NULL, NULL, NULL);
  g_assert_nonnull(input);
  output = g_file_new_for_path(argv[2]);
  g_autoptr(AdwApplication) app = adw_application_new("dev.lemmy.swash.FinishTest", 0);
  g_application_set_resource_base_path(G_APPLICATION(app), "/dev/lemmy/swash");
  g_signal_connect(app, "activate", G_CALLBACK(activate), NULL);
  int status = g_application_run(G_APPLICATION(app), 1, argv);
  g_bytes_unref(input);
  g_object_unref(output);
  return status;
}
