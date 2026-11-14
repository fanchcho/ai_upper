cmake_minimum_required(VERSION 3.25)
project(AiUpperLauncher LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(AI_UPPER_LAUNCHER_CONSOLE "Build a console-subsystem launcher for debugging the packaged application." OFF)

if(NOT PYSTAND_PYTHON_INCLUDE)
  message(FATAL_ERROR "PYSTAND_PYTHON_INCLUDE is required (PBS target SDK include directory)")
endif()

add_executable(AiUpper src/main.cpp src/AiUpper.cpp src/AiUpper.h)
target_include_directories(AiUpper PRIVATE "${PYSTAND_PYTHON_INCLUDE}")

if(AI_UPPER_APP_NAME)
  # The application name is compiled in at packaging time. The launcher cannot
  # read it from its own filename: the executable is allowed to be renamed.
  target_compile_definitions(AiUpper PRIVATE AI_UPPER_APP_NAME="${AI_UPPER_APP_NAME}")
endif()

if(AI_UPPER_EMBEDDED_SOURCE)
  # Generated at packaging time: the translation unit that carries the
  # application entry and the smoke program. A packaged launcher then runs
  # without a script next to it, and the define is what tells AiUpper.cpp the
  # symbols exist. A launcher built by hand has neither, so the file chain is
  # what resolves its entry.
  target_sources(AiUpper PRIVATE "${AI_UPPER_EMBEDDED_SOURCE}")
  target_compile_definitions(AiUpper PRIVATE AI_UPPER_HAS_EMBEDDED_SOURCE)
endif()

if(WIN32)
  # A packaged application must not open a console window when it is started
  # from Explorer. The launcher attaches to the parent console instead when one
  # exists, so diagnostics still reach cmd.exe and CI logs. The console build is
  # the debugging escape hatch: it keeps stdout/stderr attached unconditionally.
  if(NOT AI_UPPER_LAUNCHER_CONSOLE)
    set_target_properties(AiUpper PROPERTIES WIN32_EXECUTABLE TRUE)
    # WIN32_EXECUTABLE only reaches MSVC's linker: it is spelled -mwindows for
    # everyone else, and clang's driver (the Zig cross build) reports it as an
    # unused argument and drops it, silently linking a console-subsystem image
    # that pops a console window for every user. Non-MSVC linkers are handed
    # the subsystem directly so the GUI launcher survives every toolchain.
    if(NOT MSVC)
      target_link_options(AiUpper PRIVATE "-Wl,--subsystem,windows")
    endif()
  else()
    target_compile_definitions(AiUpper PRIVATE AI_UPPER_CONSOLE)
  endif()
  if(MSVC)
    # CPython 3.8's pyerrors.h aliases snprintf to _snprintf unless
    # HAVE_SNPRINTF is defined, assuming the MSVC CRT predates C99. VS 2015+
    # provides snprintf, and VS 18 no longer puts _snprintf into namespace
    # std, so std::snprintf in AiUpper.cpp expanded to std::_snprintf and
    # failed with C2039. The Zig frontend already passes this define for
    # MinGW; the native MSVC build needs it here.
    target_compile_definitions(AiUpper PRIVATE HAVE_SNPRINTF)
  endif()
  # Static CRT: the launcher must start on a machine without the Visual C++
  # redistributable, and it must not add a second MSVCRT to a process that
  # already hosts the embedded CPython runtime.
  set_property(TARGET AiUpper PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
  # CommandLineToArgvW: the wide command line is the only lossless source of a
  # non-ASCII path.
  target_link_libraries(AiUpper PRIVATE shell32)
  if(AI_UPPER_RESOURCE_RC)
    enable_language(RC)
    target_sources(AiUpper PRIVATE "${AI_UPPER_RESOURCE_RC}")
  endif()
else()
  target_link_libraries(AiUpper PRIVATE ${CMAKE_DL_LIBS})
endif()

if(APPLE)
  # CFUserNotification: a fatal error in a bundle started from Finder has no
  # terminal to report to.
  target_link_libraries(AiUpper PRIVATE "-framework CoreFoundation")
endif()
