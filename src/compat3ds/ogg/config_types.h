#ifndef SOH3DS_OGG_CONFIG_TYPES_H
#define SOH3DS_OGG_CONFIG_TYPES_H

/* The 3DS target uses the vendored codec headers with excluded_stubs.cpp,
 * without configuring libogg itself. Supply the fixed-width types normally
 * generated from libogg's config_types.h.in so clean builds need no host
 * configure step or generated files in third_party. */
#include <stdint.h>

typedef int16_t ogg_int16_t;
typedef uint16_t ogg_uint16_t;
typedef int32_t ogg_int32_t;
typedef uint32_t ogg_uint32_t;
typedef int64_t ogg_int64_t;
typedef uint64_t ogg_uint64_t;

#endif
