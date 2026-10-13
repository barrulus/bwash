#include "editor-utils.h"
#include "icons.h"
#include "stroke.h"

#include <glib.h>
#include <stdint.h>

static void
test_icon_strokes(void)
{
  const GdkRGBA color = {0.2, 0.6, 1.0, 0.75};

  for (int icon = 0; icon < SWASH_ICON_COUNT; icon++) {
    SwashStroke *stroke = swash_stroke_new(SWASH_TOOL_ICON, 64, &color, NULL, 0);
    stroke->icon = icon;
    swash_stroke_add_point(stroke, 48, 48);
    SwashStroke *copy = swash_stroke_copy(stroke);
    swash_stroke_free(stroke);
    g_assert_cmpint(copy->icon, ==, icon);
    g_assert_cmpint(swash_icon_from_key(swash_icon_key(icon)), ==, icon);

    cairo_surface_t *surface = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, 96, 96);
    cairo_t *cr = cairo_create(surface);
    swash_stroke_render(cr, copy, NULL, 0);
    g_assert_cmpint(cairo_status(cr), ==, CAIRO_STATUS_SUCCESS);
    cairo_surface_flush(surface);
    unsigned char *data = cairo_image_surface_get_data(surface);
    int stride = cairo_image_surface_get_stride(surface);
    int painted = 0;
    for (int y = 0; y < 96; y++) {
      for (int x = 0; x < 96; x++) {
        uint32_t pixel = ((uint32_t *) (data + y * stride))[x];
        if (pixel == 0)
          continue;
        painted++;
        /* Every icon fits its selection/eraser bounds and respects alpha. */
        g_assert_cmpint(x, >=, 16);
        g_assert_cmpint(x, <, 80);
        g_assert_cmpint(y, >=, 16);
        g_assert_cmpint(y, <, 80);
        g_assert_cmpint(pixel >> 24, <=, 192);
        g_assert_cmpint(pixel & 0xff, >, (pixel >> 16) & 0xff);
      }
    }
    g_assert_cmpint(painted, >, 100);
    g_assert_true(swash_stroke_hit_test(copy, 48, 48, 0));
    g_assert_false(swash_stroke_hit_test(copy, 90, 90, 0));
    g_assert_true(swash_stroke_intersects_segment(copy, 0, 48, 96, 48, 0));
    g_assert_false(swash_stroke_intersects_segment(copy, 0, 0, 96, 0, 0));
    swash_stroke_offset(copy, 100, 50);
    double x, y, w, h;
    swash_stroke_get_bounds(copy, &x, &y, &w, &h);
    g_assert_cmpfloat(x, ==, 116);
    g_assert_cmpfloat(y, ==, 66);
    g_assert_cmpfloat(w, ==, 64);
    g_assert_cmpfloat(h, ==, 64);
    g_assert_false(swash_stroke_hit_test(copy, 48, 48, 0));
    g_assert_true(swash_stroke_hit_test(copy, 148, 98, 0));
    cairo_destroy(cr);
    cairo_surface_destroy(surface);
    swash_stroke_free(copy);
  }
}

static void
test_size_presets(void)
{
  g_assert_cmpfloat(swash_tool_size_preset(SWASH_TOOL_BRUSH, 0.5), ==, 3.0);
  g_assert_cmpfloat(swash_tool_size_preset(SWASH_TOOL_BRUSH, 1.0), ==, 6.0);
  g_assert_cmpfloat(swash_tool_size_preset(SWASH_TOOL_BRUSH, 2.0), ==, 12.0);
  g_assert_cmpfloat(swash_tool_size_preset(SWASH_TOOL_TEXT, 0.5), ==, 12.0);
  g_assert_cmpfloat(swash_tool_size_preset(SWASH_TOOL_TEXT, 2.0), ==, 48.0);
}

static void
test_crop_rect(void)
{
  double left = 90.2;
  double top = 60.8;
  double right = 10.5;
  double bottom = 20.1;
  int width;
  int height;

  swash_crop_rect_normalize(&left, &top, &right, &bottom);
  g_assert_cmpfloat(left, ==, 10.5);
  g_assert_cmpfloat(top, ==, 20.1);
  g_assert_cmpfloat(right, ==, 90.2);
  g_assert_cmpfloat(bottom, ==, 60.8);

  swash_crop_rect_dimensions(left, top, right, bottom, &width, &height);
  g_assert_cmpint(width, ==, 81);
  g_assert_cmpint(height, ==, 41);
}

static void
test_shortcut_conflicts(void)
{
  g_assert_true(swash_accelerators_conflict("<Primary>c", "<Control>C"));
  g_assert_false(swash_accelerators_conflict("<Primary>c", "c"));
  g_assert_false(swash_accelerators_conflict("", "<Primary>c"));
  g_assert_false(swash_accelerators_conflict("not-an-accelerator", "<Primary>c"));
}

static void
test_stroke_sampling(void)
{
  const SwashPoint origin = { 0.0, 0.0 };
  const SwashPoint nearby = { 2.0, 1.0 };
  const SwashPoint distant = { 3.0, 0.0 };
  const SwashPoint straight = { 6.0, 0.1 };
  const SwashPoint corner = { 3.0, 3.0 };
  const SwashPoint reverse = { 1.0, 0.0 };

  g_assert_false(swash_point_is_far_enough(&origin, &nearby, 2.5));
  g_assert_true(swash_point_is_far_enough(&origin, &distant, 2.5));
  g_assert_true(swash_point_can_simplify(&origin, &distant, &straight, 0.75));
  g_assert_false(swash_point_can_simplify(&origin, &distant, &corner, 0.75));
  g_assert_false(swash_point_can_simplify(&origin, &distant, &reverse, 0.75));
}

int
main(int argc,
     char **argv)
{
  g_test_init(&argc, &argv, NULL);
  g_test_add_func("/editor/size-presets", test_size_presets);
  g_test_add_func("/editor/crop-rect", test_crop_rect);
  g_test_add_func("/editor/shortcut-conflicts", test_shortcut_conflicts);
  g_test_add_func("/editor/stroke-sampling", test_stroke_sampling);
  g_test_add_func("/editor/icon-strokes", test_icon_strokes);
  return g_test_run();
}
