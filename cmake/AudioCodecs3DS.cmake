# Blinky policy adapter to the unmodified public Opus/opusfile CMake APIs.
include_guard(GLOBAL)
if(NOT N3DS OR NOT TARGET Ogg::ogg)
    message(FATAL_ERROR "The ARM11 codec build requires the 3DS toolchain and Ogg::ogg")
endif()
get_filename_component(_codec_sources "${CMAKE_CURRENT_LIST_DIR}/../third_party" ABSOLUTE)
foreach(_option BUILD_TESTING OPUS_BUILD_SHARED_LIBRARY OPUS_BUILD_TESTING OPUS_BUILD_PROGRAMS
        OPUS_USE_NEON OPUS_MAY_HAVE_NEON OPUS_PRESUME_NEON OPUS_DRED OPUS_OSCE
        OPUS_FLOAT_APPROX OPUS_FAST_MATH OPUS_INSTALL_PKG_CONFIG_MODULE OP_DISABLE_FLOAT_API)
    set(${_option} OFF CACHE BOOL "ARM11 codec policy" FORCE)
endforeach()
foreach(_option OPUS_DISABLE_INTRINSICS OPUS_FIXED_POINT OPUS_ENABLE_FLOAT_API
        OPUS_INSTALL_CMAKE_CONFIG_MODULE OP_DISABLE_HTTP OP_DISABLE_EXAMPLES OP_DISABLE_DOCS OP_FIXED_POINT)
    set(${_option} ON CACHE BOOL "ARM11 codec policy" FORCE)
endforeach()
add_subdirectory("${_codec_sources}/opus" "${CMAKE_CURRENT_BINARY_DIR}/third_party/opus" EXCLUDE_FROM_ALL)
# The public API must use the same int32_t typedef for C89 and C99 consumers.
target_compile_definitions(opus PUBLIC HAVE_STDINT_H=1)
set(_opus_installed_spelling "${CMAKE_CURRENT_BINARY_DIR}/codec-include")
file(MAKE_DIRECTORY "${_opus_installed_spelling}/opus")
foreach(_public_header opus opus_types opus_defines opus_multistream opus_projection opus_custom)
    file(GENERATE OUTPUT "${_opus_installed_spelling}/opus/${_public_header}.h"
        CONTENT "#pragma once\n#include <${_public_header}.h>\n")
endforeach()
target_include_directories(opus INTERFACE "$<BUILD_INTERFACE:${_opus_installed_spelling}>")
add_subdirectory("${_codec_sources}/opusfile" "${CMAKE_CURRENT_BINARY_DIR}/third_party/opusfile" EXCLUDE_FROM_ALL)
target_compile_definitions(opusfile PRIVATE OP_DISABLE_HTTP=1)