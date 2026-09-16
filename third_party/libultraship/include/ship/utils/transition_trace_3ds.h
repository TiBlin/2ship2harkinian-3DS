#pragma once

#include <stdint.h>

// The runtime owns the logger. Other archives may use these hooks without
// requiring it; the implementation opts out of weak linkage explicitly.
#ifdef SOH3DS_TRANSITION_TRACE_IMPLEMENTATION
#define SOH3DS_TRANSITION_TRACE_LINKAGE
#else
#define SOH3DS_TRANSITION_TRACE_LINKAGE __attribute__((weak))
#endif

#ifdef __cplusplus
extern "C" {
#endif
void Soh3dsTransitionTraceArm(void) SOH3DS_TRANSITION_TRACE_LINKAGE;
void Soh3dsTransitionTraceEvent(const char* stage, uint32_t value) SOH3DS_TRANSITION_TRACE_LINKAGE;
#ifdef __cplusplus
}
#endif

#undef SOH3DS_TRANSITION_TRACE_LINKAGE
