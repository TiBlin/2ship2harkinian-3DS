cmake_minimum_required(VERSION 3.26)
project(TwoShip3DS VERSION 5.0.1 LANGUAGES C CXX)
if(NOT N3DS)
    message(FATAL_ERROR "Use -DCMAKE_TOOLCHAIN_FILE=cmake/3DS.cmake with DEVKITPRO set")
endif()
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
set(PORTLIBS "${DEVKITPRO}/portlibs/3ds")
set(MM_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/third_party/2ship")
set(MM_DIR "${MM_ROOT}/mm")
set(LUS_DIR "${CMAKE_CURRENT_SOURCE_DIR}/third_party/libultraship")
set(LUS_BUILD "${LUS_DIR}/build-3ds" CACHE PATH "Matching V7 LUS build")
set(DEPS "${CMAKE_CURRENT_SOURCE_DIR}/third_party/build-deps")
option(TWOSHIP3DS_EMULATOR_SAFE "Skip New 3DS CPU service in emulators" OFF)
option(TWOSHIP3DS_MEMORY_WATCH "Diagnostic: stop bulk writes over game-state pointers" OFF)
add_compile_definitions(CONTROLLERBUTTONS_T=uint32_t F3DEX_GBI_2 NDEBUG
    INCLUDE_GAME_PRINTF LOG_LEVEL_GAME_PRINTS=6 NON_MATCHING NON_EQUIVALENT)
include("${MM_ROOT}/CMake/2ship-cvars.cmake")
file(READ "${MM_ROOT}/CMake/lus-cvars.cmake" _cvars)
string(REPLACE "include(\"libultraship/cmake/cvars.cmake\")" "" _cvars "${_cvars}")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/lus-cvars-local.cmake" "${_cvars}")
include("${CMAKE_CURRENT_BINARY_DIR}/lus-cvars-local.cmake")
include("${LUS_DIR}/cmake/cvars.cmake")

set(PROJECT_BUILD_NAME "Battler Bravo / 3DS experimental V7 base")
set(PROJECT_TEAM "HarbourMasters; 3DS V7 contributors")
set(CMAKE_PROJECT_GIT_BRANCH "3ds-experimental")
set(CMAKE_PROJECT_GIT_COMMIT_HASH "6bfd6a3")
set(CMAKE_PROJECT_GIT_COMMIT_TAG "")
configure_file("${MM_DIR}/src/boot/build.c.in" "${CMAKE_CURRENT_BINARY_DIR}/mm-build.c" @ONLY)

set(COMMON_INCLUDES
    "${MM_DIR}/include" "${MM_DIR}/include/PR" "${MM_DIR}" "${MM_DIR}/src"
    "${MM_DIR}/2s2h" "${MM_DIR}/assets"
    "${LUS_DIR}/include" "${LUS_DIR}/src"
    "${DEPS}/threadpool/include" "${DEPS}/imgui" "${DEPS}/imgui/backends"
    "${DEPS}/stb" "${LUS_BUILD}/_deps/stb"
    "${PORTLIBS}/include" "${PORTLIBS}/include/SDL2")

file(GLOB_RECURSE MM_C CONFIGURE_DEPENDS "${MM_DIR}/src/*.c")
list(FILTER MM_C EXCLUDE REGEX "/src/(dmadata|elf_message|libultra)/")
list(FILTER MM_C EXCLUDE REGEX "/src/boot/build.c$")
add_library(mm_decomp STATIC ${MM_C} "${CMAKE_CURRENT_BINARY_DIR}/mm-build.c")
target_include_directories(mm_decomp PRIVATE ${COMMON_INCLUDES})
target_compile_options(mm_decomp PRIVATE -Os -w -fpermissive)
foreach(hot z_actor z_collision_check z_bgcheck sys_matrix z_skelanime z_skin_matrix z_camera z_lights z_play z_room z_scene z_view)
    if(EXISTS "${MM_DIR}/src/code/${hot}.c")
        set_source_files_properties("${MM_DIR}/src/code/${hot}.c" PROPERTIES COMPILE_OPTIONS -O2)
    endif()
endforeach()

set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(INSTALL_DOCS OFF CACHE BOOL "" FORCE)
add_subdirectory(third_party/libogg EXCLUDE_FROM_ALL)
include(cmake/AudioCodecs3DS.cmake)
add_subdirectory(third_party/libvorbis EXCLUDE_FROM_ALL)
set(PNG_SHARED OFF CACHE BOOL "" FORCE)
set(PNG_STATIC ON CACHE BOOL "" FORCE)
set(PNG_TESTS OFF CACHE BOOL "" FORCE)
set(PNG_TOOLS OFF CACHE BOOL "" FORCE)
set(PNG_EXECUTABLES OFF CACHE BOOL "" FORCE)
set(PNG_ARM_NEON off CACHE STRING "" FORCE)
set(ZLIB_LIBRARY "${PORTLIBS}/lib/libzlibstatic.a" CACHE FILEPATH "" FORCE)
set(ZLIB_INCLUDE_DIR "${PORTLIBS}/include" CACHE PATH "" FORCE)
add_subdirectory(third_party/libpng EXCLUDE_FROM_ALL)
file(GLOB_RECURSE MM_CPP CONFIGURE_DEPENDS "${MM_DIR}/2s2h/*.cpp" "${MM_DIR}/2s2h/*.c")
list(FILTER MM_CPP EXCLUDE REGEX "/2s2h/Extractor/")
add_library(mm_enhancements STATIC ${MM_CPP})
target_include_directories(mm_enhancements PRIVATE ${COMMON_INCLUDES}
    "${CMAKE_CURRENT_SOURCE_DIR}/third_party/dr_libs")
target_compile_options(mm_enhancements PRIVATE -Os -w -fpermissive)
target_link_libraries(mm_enhancements PUBLIC vorbisfile png_static opusfile)
target_precompile_headers(mm_enhancements PRIVATE
    "$<$<COMPILE_LANGUAGE:CXX>:<libultraship/bridge/consolevariablebridge.h$<ANGLE-R>>"
    "$<$<COMPILE_LANGUAGE:CXX>:<ship/Context.h$<ANGLE-R>>"
    "$<$<COMPILE_LANGUAGE:CXX>:<ship/resource/ResourceManager.h$<ANGLE-R>>"
    "$<$<COMPILE_LANGUAGE:CXX>:<ship/window/Window.h$<ANGLE-R>>"
    "$<$<COMPILE_LANGUAGE:CXX>:<spdlog/spdlog.h$<ANGLE-R>>"
    "$<$<COMPILE_LANGUAGE:CXX>:<string$<ANGLE-R>>"
    "$<$<COMPILE_LANGUAGE:CXX>:<vector$<ANGLE-R>>"
    "$<$<COMPILE_LANGUAGE:CXX>:<map$<ANGLE-R>>"
    "$<$<COMPILE_LANGUAGE:CXX>:<unordered_map$<ANGLE-R>>"
    "$<$<COMPILE_LANGUAGE:CXX>:<filesystem$<ANGLE-R>>"
    "$<$<COMPILE_LANGUAGE:CXX>:<fstream$<ANGLE-R>>"
    "$<$<COMPILE_LANGUAGE:CXX>:<algorithm$<ANGLE-R>>"
    "$<$<COMPILE_LANGUAGE:CXX>:<functional$<ANGLE-R>>"
    "$<$<COMPILE_LANGUAGE:CXX>:<variant$<ANGLE-R>>"
    "$<$<COMPILE_LANGUAGE:CXX>:${MM_DIR}/2s2h/GameInteractor/GameInteractor.h>"
    "$<$<COMPILE_LANGUAGE:CXX>:${MM_DIR}/include/variables.h>"
    "$<$<COMPILE_LANGUAGE:CXX>:${MM_DIR}/include/functions.h>"
    "$<$<COMPILE_LANGUAGE:CXX>:${MM_DIR}/include/macros.h>"
    "$<$<COMPILE_LANGUAGE:CXX>:${MM_DIR}/include/z64.h>"
    "$<$<COMPILE_LANGUAGE:C>:${MM_DIR}/include/ultra64.h>"
    "$<$<COMPILE_LANGUAGE:C>:${MM_DIR}/include/global.h>"
    "$<$<COMPILE_LANGUAGE:C>:${MM_DIR}/include/z64.h>"
    "$<$<COMPILE_LANGUAGE:C>:${MM_DIR}/include/macros.h>"
    "$<$<COMPILE_LANGUAGE:C>:${MM_DIR}/include/functions.h>"
    "$<$<COMPILE_LANGUAGE:C>:${MM_DIR}/include/variables.h>"
)
set_source_files_properties("${MM_DIR}/2s2h/mixer.c" PROPERTIES COMPILE_OPTIONS -O2 SKIP_PRECOMPILE_HEADERS ON)

set(SHBIN "${CMAKE_CURRENT_BINARY_DIR}/fast3d_passthrough.shbin")
set(SHADER_C "${CMAKE_CURRENT_BINARY_DIR}/fast3d_passthrough_shbin.c")
add_custom_command(OUTPUT "${SHADER_C}"
    COMMAND "${DEVKITPRO}/tools/bin/picasso" -o "${SHBIN}"
        "${CMAKE_CURRENT_SOURCE_DIR}/platform/3ds/shaders/fast3d_passthrough.v.pica"
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/scripts/bin2c.py"
        "${SHBIN}" "${SHADER_C}" fast3d_passthrough_shbin
    DEPENDS platform/3ds/shaders/fast3d_passthrough.v.pica scripts/bin2c.py VERBATIM)
add_library(renderer_v7 STATIC platform/3ds/source/gfx_citro3d.cpp
    platform/3ds/source/gfx_window_manager_3ds.cpp src/mk_gfx_factory.cpp "${SHADER_C}")
target_include_directories(renderer_v7 PRIVATE ${COMMON_INCLUDES} src platform/3ds/include
    "${CMAKE_CURRENT_BINARY_DIR}")
target_compile_options(renderer_v7 PRIVATE -O3 -fomit-frame-pointer -fno-strict-aliasing -w)
if(TWOSHIP3DS_EMULATOR_SAFE)
    target_compile_definitions(renderer_v7 PRIVATE SOH3DS_EMULATOR_SAFE)
endif()

if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/src/port3ds/runtime_3ds.cpp")
    add_executable(2ship_3ds src/port3ds/runtime_3ds.cpp src/port3ds/backend_stubs.cpp src/port3ds/controls_3ds.cpp
        src/compat3ds/logging_3ds.cpp src/compat3ds/sleep_3ds.cpp)
    set_target_properties(2ship_3ds PROPERTIES OUTPUT_NAME "2ship-3ds.elf")
    target_include_directories(2ship_3ds PRIVATE ${COMMON_INCLUDES} src src/compat3ds src/port3ds)
    target_compile_options(2ship_3ds PRIVATE -Os -Wall -Wextra)
    target_link_options(2ship_3ds PRIVATE -Wl,--wrap=__syscall_thread_create -Wl,--wrap=threadCreate
        "-Wl,-Map=${CMAKE_CURRENT_BINARY_DIR}/2ship-3ds.map")
    if(TWOSHIP3DS_MEMORY_WATCH)
        target_sources(2ship_3ds PRIVATE src/port3ds/memory_watch.cpp)
        set_property(SOURCE "${MM_DIR}/2s2h/mixer.c" APPEND PROPERTY
            COMPILE_DEFINITIONS TWOSHIP3DS_MEMORY_WATCH=1)
        set_property(SOURCE "${MM_DIR}/2s2h/mixer.c" APPEND PROPERTY COMPILE_OPTIONS -g)
        set_property(SOURCE "${MM_DIR}/src/audio/lib/synthesis.c" APPEND PROPERTY
            COMPILE_OPTIONS -g -O0 -fno-omit-frame-pointer)
        set_property(SOURCE "${MM_DIR}/src/code/graph.c" APPEND PROPERTY
            COMPILE_DEFINITIONS TWOSHIP3DS_MEMORY_WATCH=1)
        target_link_options(2ship_3ds PRIVATE
            -Wl,--wrap=memset -Wl,--wrap=memcpy -Wl,--wrap=memmove)
        # Keep the diagnostic's own formatting allocation-free and out of libc.
        set_source_files_properties(src/port3ds/memory_watch.cpp PROPERTIES COMPILE_OPTIONS
            "-fno-builtin;-fno-tree-loop-distribute-patterns")
    endif()
    target_link_libraries(2ship_3ds PRIVATE -Wl,--start-group
        -Wl,--whole-archive mm_enhancements -Wl,--no-whole-archive
        mm_decomp renderer_v7 "${LUS_BUILD}/src/libultraship.a"
        "${LUS_BUILD}/libImGui.a" "${LUS_BUILD}/_deps/prism-build/libprism.a"
        "${LUS_BUILD}/libstb.a" "${LUS_BUILD}/libmonocypher.a"
        vorbisfile "${PORTLIBS}/lib/libzip.a" "${PORTLIBS}/lib/libspdlog.a"
        "${PORTLIBS}/lib/libtinyxml2.a" "${PORTLIBS}/lib/libzlibstatic.a"
        "${PORTLIBS}/lib/libSDL2.a" citro3d ctru m -Wl,--end-group)
    add_custom_command(TARGET 2ship_3ds POST_BUILD
        COMMAND "${DEVKITPRO}/tools/bin/3dsxtool" "$<TARGET_FILE:2ship_3ds>"
            "${CMAKE_CURRENT_BINARY_DIR}/2ship-3ds.3dsx" VERBATIM)
endif()
list(LENGTH MM_C MM_C_COUNT)
list(LENGTH MM_CPP MM_CPP_COUNT)
message(STATUS "2Ship ARM sources: ${MM_C_COUNT} decomp + ${MM_CPP_COUNT} enhancements")
