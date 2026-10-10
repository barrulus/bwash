/* Drive the real file chooser through GTK rather than relying on simulated
 * typing and filename completion. Run inside the GUI test's private session. */
#include "window-private.h"

static SwashWindow *original;
static GFile *input;
static GFile *destination;
static GtkWindow *chooser;
static guint phase;

static gboolean
drive_chooser(gpointer data)
{
  GtkApplication *app = GTK_APPLICATION(data);

  if (phase == 0 || phase == 3) {
    GListModel *toplevels = gtk_window_get_toplevels();
    for (guint i = 0; i < g_list_model_get_n_items(toplevels); i++) {
      g_autoptr(GtkWindow) window = g_list_model_get_item(toplevels, i);
      if (GTK_IS_FILE_CHOOSER(window)) {
        g_autoptr(GError) error = NULL;
        chooser = g_object_ref(window);
        g_assert_true(gtk_file_chooser_set_file(GTK_FILE_CHOOSER(chooser), input, &error));
        g_assert_no_error(error);
        phase++;
        break;
      }
    }
    return G_SOURCE_CONTINUE;
  }

  if (phase == 1 || phase == 4) {
    g_autoptr(GFile) selected = gtk_file_chooser_get_file(GTK_FILE_CHOOSER(chooser));
    if (selected == NULL || !g_file_equal(selected, input))
      return G_SOURCE_CONTINUE;
    gtk_dialog_response(GTK_DIALOG(chooser), GTK_RESPONSE_ACCEPT);
    g_clear_object(&chooser);
    phase++;
    return G_SOURCE_CONTINUE;
  }

  guint count = 0;
  SwashWindow *opened = NULL;
  for (GList *item = gtk_application_get_windows(app); item != NULL; item = item->next) {
    if (SWASH_IS_WINDOW(item->data)) {
      count++;
      if (item->data != original)
        opened = item->data;
    }
  }

  if (phase == 2) {
    if (count != 2)
      return G_SOURCE_CONTINUE;
    g_assert_nonnull(opened);
    g_assert_cmpint(gdk_texture_get_width(original->texture), ==, 64);
    g_assert_cmpint(gdk_texture_get_height(original->texture), ==, 48);
    g_assert_true(swash_document_can_undo(original->document));
    g_assert_true(swash_document_has_unsaved_changes(original->document));
    g_assert_true(g_file_equal(original->output_file, destination));
    g_assert_cmpint(gdk_texture_get_width(opened->texture), ==, 48);
    g_assert_cmpint(gdk_texture_get_height(opened->texture), ==, 64);
    g_assert_false(swash_document_can_undo(opened->document));
    g_assert_null(opened->output_file);
    gtk_window_destroy(GTK_WINDOW(opened));

    /* The chooser may reuse a genuinely empty editor. */
    g_assert_true(swash_window_open_file(original, NULL, NULL));
    gtk_widget_activate_action(GTK_WIDGET(original), "win.open", NULL);
    phase = 3;
    return G_SOURCE_CONTINUE;
  }

  if (original->texture == NULL)
    return G_SOURCE_CONTINUE;
  g_assert_cmpuint(count, ==, 1);
  g_assert_cmpint(gdk_texture_get_width(original->texture), ==, 48);
  g_assert_false(swash_document_can_undo(original->document));
  gtk_window_destroy(GTK_WINDOW(original));
  g_print("PASS: file chooser preserves populated documents and reuses empty editors\n");
  return G_SOURCE_REMOVE;
}

static void
activate(GApplication *app, gpointer data)
{
  g_autoptr(GError) error = NULL;
  (void) data;

  original = swash_window_new(ADW_APPLICATION(app));
  g_assert_true(swash_window_open_file(original, input, &error));
  g_assert_no_error(error);
  swash_window_set_output_file(original, destination);
  gtk_widget_activate_action(GTK_WIDGET(original), "win.rotate-counter-clockwise", NULL);
  gtk_window_present(GTK_WINDOW(original));
  gtk_widget_activate_action(GTK_WIDGET(original), "win.open", NULL);
  g_timeout_add(50, drive_chooser, app);
}

int
main(int argc, char **argv)
{
  g_assert_cmpint(argc, ==, 2);
  input = g_file_new_for_path(argv[1]);
  destination = g_file_new_for_path("/unused-dialog-test-output.png");
  g_autoptr(AdwApplication) app = adw_application_new("dev.lemmy.swash.OpenTest", 0);
  g_application_set_resource_base_path(G_APPLICATION(app), "/dev/lemmy/swash");
  g_signal_connect(app, "activate", G_CALLBACK(activate), NULL);
  int status = g_application_run(G_APPLICATION(app), 1, argv);
  g_object_unref(input);
  g_object_unref(destination);
  return status;
}
