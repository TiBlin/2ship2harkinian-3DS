# Build the real local Opus and Ogg Opus decoders for ARM11. Include this after
# adding libogg; link consumers to OpusFile::opusfile (or opusfile).
include_guard(GLOBAL)
if(NOT N3DS)
    message(FATAL_ERROR "AudioCodecs3DS requires the 3DS ARM toolchain")
endif()
if(NOT TARGET Ogg::ogg)
    message(FATAL_ERROR "Add third_party/libogg before including AudioCodecs3DS")
endif()
get_filename_component(TWOSHIP_CODEC_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)

set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(OPUS_BUILD_SHARED_LIBRARY OFF CACHE BOOL "" FORCE)
set(OPUS_BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(OPUS_BUILD_PROGRAMS OFF CACHE BOOL "" FORCE)
set(OPUS_DISABLE_INTRINSICS ON CACHE BOOL "" FORCE)
set(OPUS_USE_NEON OFF CACHE BOOL "" FORCE)
set(OPUS_MAY_HAVE_NEON OFF CACHE BOOL "" FORCE)
set(OPUS_PRESUME_NEON OFF CACHE BOOL "" FORCE)
set(OPUS_DRED OFF CACHE BOOL "" FORCE)
set(OPUS_OSCE OFF CACHE BOOL "" FORCE)
set(OPUS_FIXED_POINT ON CACHE BOOL "" FORCE)
set(OPUS_ENABLE_FLOAT_API ON CACHE BOOL "" FORCE)
set(OPUS_FLOAT_APPROX OFF CACHE BOOL "" FORCE)
set(OPUS_FAST_MATH OFF CACHE BOOL "" FORCE)
set(OPUS_INSTALL_PKG_CONFIG_MODULE OFF CACHE BOOL "" FORCE)
# opusfile declares an install export referencing Opus; keep Opus in its own
# export set even though this embedded build never runs cmake --install.
set(OPUS_INSTALL_CMAKE_CONFIG_MODULE ON CACHE BOOL "" FORCE)
set(OP_DISABLE_HTTP ON CACHE BOOL "" FORCE)
set(OP_DISABLE_EXAMPLES ON CACHE BOOL "" FORCE)
set(OP_DISABLE_DOCS ON CACHE BOOL "" FORCE)
set(OP_DISABLE_FLOAT_API OFF CACHE BOOL "" FORCE)
set(OP_FIXED_POINT ON CACHE BOOL "" FORCE)

add_subdirectory("${TWOSHIP_CODEC_ROOT}/third_party/opus" "${CMAKE_CURRENT_BINARY_DIR}/third_party/opus" EXCLUDE_FROM_ALL)

# Opus's C89 fallback uses int while devkitARM's int32_t is long. Its C99
# objects and every opusfile/game consumer must choose the same public types.
target_compile_definitions(opus PUBLIC HAVE_STDINT_H=1)

# Source consumers use both <opus/opus.h> and <opus_multistream.h>. Upstream's
# build interface exposes only flat headers. Add forwarding headers for the
# installed spelling without replacing the real public API declarations.
set(TWOSHIP_CODEC_INCLUDE "${CMAKE_CURRENT_BINARY_DIR}/codec-include")
file(MAKE_DIRECTORY "${TWOSHIP_CODEC_INCLUDE}/opus")
foreach(TWOSHIP_OPUS_HEADER opus.h opus_types.h opus_defines.h opus_multistream.h opus_projection.h opus_custom.h)
    file(GENERATE OUTPUT "${TWOSHIP_CODEC_INCLUDE}/opus/${TWOSHIP_OPUS_HEADER}"
        CONTENT "#pragma once\n#include <${TWOSHIP_OPUS_HEADER}>\n")
endforeach()
target_include_directories(opus INTERFACE "$<BUILD_INTERFACE:${TWOSHIP_CODEC_INCLUDE}>")

add_subdirectory("${TWOSHIP_CODEC_ROOT}/third_party/opusfile" "${CMAKE_CURRENT_BINARY_DIR}/third_party/opusfile" EXCLUDE_FROM_ALL)

# opusurl is intentionally not a dependency of opusfile. HTTP and TLS are not
# built or linked by any 2Ship target; all custom audio comes from local files.
target_compile_definitions(opusfile PRIVATE OP_DISABLE_HTTP=1)
