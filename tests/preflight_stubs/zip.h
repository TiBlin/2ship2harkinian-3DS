#pragma once
// Only the libzip call boundary is replaced by the portable preflight test.
// Production archive_checks.h is compiled unchanged against these declarations.
#include <cstdint>
using zip_int64_t = std::int64_t;
using zip_uint64_t = std::uint64_t;
using zip_flags_t = std::uint32_t;
struct zip_t {};
struct zip_file_t {};
struct zip_stat_t { zip_uint64_t size; };
constexpr int ZIP_RDONLY = 16;
zip_t* zip_open(const char*, int, int*);
zip_int64_t zip_get_num_entries(zip_t*, zip_flags_t);
int zip_stat(zip_t*, const char*, zip_flags_t, zip_stat_t*);
zip_file_t* zip_fopen(zip_t*, const char*, zip_flags_t);
zip_int64_t zip_fread(zip_file_t*, void*, zip_uint64_t);
int zip_fclose(zip_file_t*);
void zip_discard(zip_t*);
