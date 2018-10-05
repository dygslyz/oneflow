#include "oneflow/core/common/util.h"
#include <cfenv>
#include "oneflow/core/common/str_util.h"
#include "oneflow/core/common/platform.h"

#ifdef PLATFORM_POSIX
#include <sys/sysinfo.h>
#endif

namespace oneflow {

#define DEFINE_ONEFLOW_STR2INT_CAST(dst_type, cast_func) \
  template<>                                             \
  dst_type oneflow_cast(const std::string& s) {          \
    char* end_ptr = nullptr;                             \
    dst_type ret = cast_func(s.c_str(), &end_ptr, 0);    \
    CHECK_EQ(*end_ptr, '\0');                            \
    return ret;                                          \
  }

DEFINE_ONEFLOW_STR2INT_CAST(long, strtol);
DEFINE_ONEFLOW_STR2INT_CAST(unsigned long, strtoul);
DEFINE_ONEFLOW_STR2INT_CAST(long long, strtoll);
DEFINE_ONEFLOW_STR2INT_CAST(unsigned long long, strtoull);

DEFINE_ONEFLOW_STR2INT_CAST(signed char, strtol);
DEFINE_ONEFLOW_STR2INT_CAST(short, strtol);
DEFINE_ONEFLOW_STR2INT_CAST(int, strtol);

DEFINE_ONEFLOW_STR2INT_CAST(unsigned char, strtoul);
DEFINE_ONEFLOW_STR2INT_CAST(unsigned short, strtoul);
DEFINE_ONEFLOW_STR2INT_CAST(unsigned int, strtoul);

int kThisMachineId = -1;

template<>
float oneflow_cast(const std::string& s) {
  char* end_ptr = nullptr;
  float ret = strtof(s.c_str(), &end_ptr);
  CHECK_EQ(*end_ptr, '\0');
  return ret;
}

template<>
double oneflow_cast(const std::string& s) {
  char* end_ptr = nullptr;
  double ret = strtod(s.c_str(), &end_ptr);
  CHECK_EQ(*end_ptr, '\0');
  return ret;
}

#ifdef PLATFORM_POSIX
COMMAND(feenableexcept(FE_ALL_EXCEPT & ~FE_INEXACT & ~FE_UNDERFLOW));
#endif

void RedirectStdoutAndStderrToGlogDir() {
  PCHECK(freopen(JoinPath(LogDir(), "stdout").c_str(), "a+", stdout));
  PCHECK(freopen(JoinPath(LogDir(), "stderr").c_str(), "a+", stderr));
}

void CloseStdoutAndStderr() {
  PCHECK(fclose(stdout) == 0);
  PCHECK(fclose(stderr) == 0);
}

size_t GetAvailableCpuMemSize() {
#ifdef PLATFORM_POSIX
  std::ifstream mem_info("/proc/meminfo");
  CHECK(mem_info.good()) << "can't open file: /proc/meminfo";
  std::string line;
  while (std::getline(mem_info, line).good()) {
    std::string token;
    const char* p = line.c_str();
    p = StrToToken(p, " ", &token);
    if (token != "MemAvailable:") { continue; }
    CHECK_NE(*p, '\0');
    p = StrToToken(p, " ", &token);
    size_t mem_available = oneflow_cast<size_t>(token);
    CHECK_NE(*p, '\0');
    p = StrToToken(p, " ", &token);
    CHECK_EQ(token, "kB");
    return mem_available * 1024;
  }
  LOG(FATAL) << "can't find MemAvailable in /proc/meminfo";
#else
  TODO();
#endif
  return 0;
}

std::string LogDir() {
  if (kThisMachineId == -1) {
    char hostname[32];  // TODO(shiyuan)
    CHECK_EQ(gethostname(hostname, sizeof(hostname)), 0);
    return (FLAGS_log_dir + "/" + std::string(hostname));
  } else {
    CHECK_GE(kThisMachineId, 0);
    return (FLAGS_log_dir + "/" + std::to_string(kThisMachineId));
  }
}

}  // namespace oneflow
