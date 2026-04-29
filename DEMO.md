# About Popup — 4K Intro Design Brief

This document captures the initial design decisions for the "About" popup, which is a
demoscene-style 4K intro invoked as a subprocess by the main Qt6 application.

## Concept

A homage to demoscene 4K intro compos. A small, decoration-free window in the centre of
the screen presenting credits, math-generated animations, and 8-bit/SID-style tracker
music, in as small a binary as possible (target: 4096 bytes compressed).

## Integration with the Qt6 application

The intro is a fully self-contained ELF binary. The Qt6 app launches it as a subprocess
and has no further involvement:

```cpp
QProcess::startDetached("about", {});
```

The intro manages its own window, render loop, and audio thread. ESC or window-close
exits via the `exit` syscall. No IPC, no shared memory, no Qt involvement.

## Display: X11, not Wayland-native

- Target X11 via libX11 + GLX.
- Wayland users are expected to run XWayland for compatibility.
- X11 is simpler to set up from raw asm (clean C ABI, well-documented socket protocol).
- Wayland-native would require the full `xdg-shell` protocol — significant extra complexity.

### No window decorations

Set `_MOTIF_WM_HINTS` or `_NET_WM_WINDOW_TYPE_SPLASH` via X11 atoms to suppress the
window manager's title bar and frame. Center the window with `XMoveWindow` after mapping.

## Graphics: GLSL + OpenGL via GLX

- Create an OpenGL context with GLX.
- All visuals live in a single GLSL fragment shader (raymarching, signed distance
  functions, procedural animation).
- Shader source is stored as a zlib-compressed blob; decompressed at runtime into a
  `malloc`'d buffer, then compiled with `glShaderSource` / `glCompileShader`.
- This means the shader (the creative content) compresses well and the host asm stub
  stays minimal.

## Audio: SID/FM softsynth → ALSA

- Spawn a `pthread` for audio output.
- Implement a minimal softsynth: square/sawtooth/triangle oscillators with ADSR envelopes.
- Note sequences hardcoded as compact byte arrays.
- Write generated PCM samples directly to ALSA via `snd_pcm_write` (`libasound`).
- No tracker file format — the "tracker" is just inline data + a tiny playback engine.

## Size budget: dynamic linking is free

Library code does not count against the 4K budget. Link dynamically against:

| Library     | Provides                          |
|-------------|-----------------------------------|
| libX11      | X11 window, event loop            |
| libGL       | OpenGL context + draw calls       |
| libGLX      | GLX context creation              |
| libz        | zlib decompression of shader blob |
| libasound   | ALSA PCM output                   |
| libpthread  | audio thread                      |
| libm        | math functions (if needed)        |

Only the ELF's own `.text` and data segments count. Bypass libc startup entirely: use
`_start` as the entry point, make syscalls directly where needed.

## Build system: Makefile (separate from Qt6/CMake)

The intro has its own `Makefile`. The Qt6 `CMakeLists.txt` invokes it as a custom
command so it builds alongside the main project:

```cmake
add_custom_target(about_intro
    COMMAND make -C ${CMAKE_SOURCE_DIR}/intro
    BYPRODUCTS ${CMAKE_SOURCE_DIR}/intro/about
)
add_dependencies(your_qt_target about_intro)
```

Typical Makefile pipeline:

```makefile
NASM      := nasm
NASMFLAGS := -f elf64
LD        := ld
LDFLAGS   := -dynamic-linker /lib64/ld-linux-x86-64.so.2 \
             -lX11 -lGL -lGLX -lz -lasound -lpthread -lm

about: about.o
	$(LD) $(LDFLAGS) -o $@ $<
	sstrip $@

about.o: about.asm
	$(NASM) $(NASMFLAGS) -o $@ $<
```

## Packing

The "4K" target typically refers to the **compressed** binary, not the raw ELF size.

- `sstrip` (from ELFkickers) — aggressively strips ELF metadata while keeping the binary runnable.
- Custom deflate packer with a small asm decompressor stub — common in Linux 4K entries.
- `smol` (by Shiz) — a linker that produces minimal ELF with only `PT_LOAD` segments;
  good alternative to a hand-crafted ELF header.
- `gzip -9` or a custom deflate packer for final size measurement.

## Reference material

- Lovebyte and Revision demoparties — Linux 4K entries with occasional source releases.
- Shiz's `smol`: https://github.com/nicowillis/smol (minimal Linux ELF linker).
- ELFkickers (`sstrip`, `rebind`, etc.): https://github.com/BR903/ELFkickers
- Shadertoy — good sandbox for developing the GLSL shader before integrating.
- "Sizecoding" wiki: http://www.sizecoding.org/wiki/Linux

## Key constraints summary

| Property         | Decision                                      |
|------------------|-----------------------------------------------|
| Target size      | ≤ 4096 bytes compressed                       |
| Display server   | X11 (XWayland for Wayland users)              |
| Graphics API     | OpenGL via GLX                                |
| Rendering        | GLSL fragment shader (raymarching / SDFs)     |
| Audio            | Softsynth → ALSA (`libasound`)                |
| Entry point      | `_start` (no libc startup)                    |
| Linking          | Dynamic (library code is free to size budget) |
| Build tool       | Makefile                                      |
| Packer           | sstrip + optional deflate packer              |
| Close            | ESC key → `exit` syscall                      |
