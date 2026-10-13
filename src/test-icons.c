#include "window-private.h"
#include "icons.h"

static gboolean
check_picker(gpointer data)
{
  SwashWindow *window = SWASH_WINDOW(data);
  GtkPopover *popover = gtk_menu_button_get_popover(window->icon_picker_button);
  GtkWidget *grid = gtk_widget_get_last_child(gtk_popover_get_child(popover));

  for (int i = 0; i < SWASH_ICON_COUNT; i++) {
    gtk_toggle_button_set_active(window->numbering_tool_button, TRUE);
    gtk_menu_button_popup(window->icon_picker_button);
    GtkWidget *button = gtk_grid_get_child_at(GTK_GRID(grid), i % 4, i / 4);
    g_assert_cmpstr(gtk_widget_get_tooltip_text(button), ==, swash_icon_name(i));
    g_signal_emit_by_name(button, "clicked");
    g_assert_cmpint(window->active_tool, ==, SWASH_TOOL_ICON);
    g_assert_cmpint(window->selected_icon, ==, i);
    g_assert_true(gtk_toggle_button_get_active(window->icon_tool_button));
    g_assert_cmpuint(swash_document_get_strokes(window->document)->len, ==, 0);
  }

  /* Leave an identifiable selection, colour and size for the next process. */
  GtkWidget *heart = gtk_grid_get_child_at(GTK_GRID(grid),
                                          SWASH_ICON_HEART % 4, SWASH_ICON_HEART / 4);
  g_signal_emit_by_name(heart, "clicked");
  const GdkRGBA green = {0.0, 1.0, 0.0, 1.0};
  gtk_color_dialog_button_set_rgba(window->color_button, &green);
  gtk_toggle_button_set_active(window->small_size_button, TRUE);
  g_assert_cmpfloat(window->tool_widths[SWASH_TOOL_ICON], ==, 16.0);
  gtk_window_close(GTK_WINDOW(window));
  g_print("PASS: all picker choices activate Icon; selection, colour and size saved\n");
  return G_SOURCE_REMOVE;
}

static void
activate(GApplication *app, gpointer data)
{
  SwashWindow *window = swash_window_new(ADW_APPLICATION(app));
  g_autoptr(GFile) source = g_file_new_for_path(data);
  g_autoptr(GError) error = NULL;
  g_assert_true(swash_window_open_file(window, source, &error));
  g_assert_no_error(error);
  gtk_window_present(GTK_WINDOW(window));
  g_timeout_add(200, check_picker, window);
}

int
main(int argc, char **argv)
{
  g_assert_cmpint(argc, ==, 2);
  g_autoptr(AdwApplication) app = adw_application_new("dev.lemmy.swash.IconTest", 0);
  g_application_set_resource_base_path(G_APPLICATION(app), "/dev/lemmy/swash");
  g_signal_connect(app, "activate", G_CALLBACK(activate), argv[1]);
  return g_application_run(G_APPLICATION(app), 1, argv);
}
