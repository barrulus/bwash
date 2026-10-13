#include "icons.h"

#include <math.h>

static const struct {
  const char *key;
  const char *name;
} icons[SWASH_ICON_COUNT] = {
  [SWASH_ICON_CHECK] = {"check", "Tick"},
  [SWASH_ICON_CROSS] = {"cross", "Cross"},
  [SWASH_ICON_WARNING] = {"warning", "Warning"},
  [SWASH_ICON_INFO] = {"info", "Information"},
  [SWASH_ICON_QUESTION] = {"question", "Question"},
  [SWASH_ICON_STAR] = {"star", "Star"},
  [SWASH_ICON_HEART] = {"heart", "Heart"},
  [SWASH_ICON_PLUS] = {"plus", "Plus"},
  [SWASH_ICON_ARROW_UP] = {"arrow-up", "Arrow up"},
  [SWASH_ICON_ARROW_RIGHT] = {"arrow-right", "Arrow right"},
  [SWASH_ICON_ARROW_DOWN] = {"arrow-down", "Arrow down"},
  [SWASH_ICON_ARROW_LEFT] = {"arrow-left", "Arrow left"},
};

const char *
swash_icon_name(SwashIcon icon)
{
  return icons[CLAMP(icon, 0, SWASH_ICON_COUNT - 1)].name;
}

const char *
swash_icon_key(SwashIcon icon)
{
  return icons[CLAMP(icon, 0, SWASH_ICON_COUNT - 1)].key;
}

SwashIcon
swash_icon_from_key(const char *key)
{
  for (int i = 0; i < SWASH_ICON_COUNT; i++)
    if (g_strcmp0(key, icons[i].key) == 0)
      return i;
  return SWASH_ICON_CHECK;
}

void
swash_icon_render(cairo_t *cr, SwashIcon icon)
{
  cairo_save(cr);
  cairo_new_path(cr);
  cairo_set_line_width(cr, 0.09);
  cairo_set_line_cap(cr, CAIRO_LINE_CAP_ROUND);
  cairo_set_line_join(cr, CAIRO_LINE_JOIN_ROUND);

  switch (icon) {
  case SWASH_ICON_CHECK:
    cairo_move_to(cr, -0.38, 0.0);
    cairo_line_to(cr, -0.1, 0.30);
    cairo_line_to(cr, 0.39, -0.32);
    break;
  case SWASH_ICON_CROSS:
    cairo_move_to(cr, -0.33, -0.33);
    cairo_line_to(cr, 0.33, 0.33);
    cairo_move_to(cr, -0.33, 0.33);
    cairo_line_to(cr, 0.33, -0.33);
    break;
  case SWASH_ICON_WARNING:
    cairo_move_to(cr, 0.0, -0.40);
    cairo_line_to(cr, 0.43, 0.36);
    cairo_line_to(cr, -0.43, 0.36);
    cairo_close_path(cr);
    cairo_move_to(cr, 0.0, -0.12);
    cairo_line_to(cr, 0.0, 0.08);
    cairo_move_to(cr, 0.0, 0.23);
    cairo_line_to(cr, 0.0, 0.23);
    break;
  case SWASH_ICON_INFO:
  case SWASH_ICON_QUESTION:
    cairo_arc(cr, 0.0, 0.0, 0.40, 0, 2 * G_PI);
    if (icon == SWASH_ICON_INFO) {
      cairo_move_to(cr, 0.0, -0.20);
      cairo_line_to(cr, 0.0, -0.20);
      cairo_move_to(cr, 0.0, -0.02);
      cairo_line_to(cr, 0.0, 0.22);
    } else {
      cairo_move_to(cr, -0.13, -0.14);
      cairo_curve_to(cr, -0.13, -0.32, 0.25, -0.29, 0.12, -0.07);
      cairo_curve_to(cr, 0.08, -0.01, 0.0, -0.01, 0.0, 0.08);
      cairo_move_to(cr, 0.0, 0.23);
      cairo_line_to(cr, 0.0, 0.23);
    }
    break;
  case SWASH_ICON_STAR:
    for (int i = 0; i < 10; i++) {
      double angle = -G_PI / 2 + i * G_PI / 5;
      double radius = i % 2 == 0 ? 0.43 : 0.19;
      if (i == 0)
        cairo_move_to(cr, radius * cos(angle), radius * sin(angle));
      else
        cairo_line_to(cr, radius * cos(angle), radius * sin(angle));
    }
    cairo_close_path(cr);
    cairo_fill(cr);
    break;
  case SWASH_ICON_HEART:
    cairo_move_to(cr, 0.0, 0.40);
    cairo_curve_to(cr, -0.85, -0.16, -0.18, -0.65, 0.0, -0.24);
    cairo_curve_to(cr, 0.18, -0.65, 0.85, -0.16, 0.0, 0.40);
    cairo_close_path(cr);
    cairo_fill(cr);
    break;
  case SWASH_ICON_PLUS:
    cairo_move_to(cr, -0.35, 0.0);
    cairo_line_to(cr, 0.35, 0.0);
    cairo_move_to(cr, 0.0, -0.35);
    cairo_line_to(cr, 0.0, 0.35);
    break;
  case SWASH_ICON_ARROW_UP:
  case SWASH_ICON_ARROW_RIGHT:
  case SWASH_ICON_ARROW_DOWN:
  case SWASH_ICON_ARROW_LEFT:
    cairo_rotate(cr, (icon - SWASH_ICON_ARROW_UP) * G_PI / 2);
    cairo_move_to(cr, 0.0, 0.38);
    cairo_line_to(cr, 0.0, -0.38);
    cairo_move_to(cr, -0.30, -0.08);
    cairo_line_to(cr, 0.0, -0.38);
    cairo_line_to(cr, 0.30, -0.08);
    break;
  default:
    break;
  }
  cairo_stroke(cr);
  cairo_restore(cr);
}
