#pragma once

#include "types.h"

const char *swash_icon_name(SwashIcon icon);
const char *swash_icon_key(SwashIcon icon);
SwashIcon swash_icon_from_key(const char *key);
/* Draw inside a unit square centred on the origin, using the current source. */
void swash_icon_render(cairo_t *cr, SwashIcon icon);
