// shtest — offline shader harness: compile, link, draw, read back a pixel.
//
// The intro has no GL error paths (a failed link just renders black), so
// this is the way to see real driver errors. glslangValidator is not enough:
// e.g. NVIDIA accepts a large dynamically indexed const array at compile
// time, then fails at link with C5041 (no bindable resource).
//
// Build: gcc -o shtest shtest.c -lX11 -lGL
// Usage: ./shtest ../shader_full.frag
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <X11/Xlib.h>
#include <GL/gl.h>
#include <GL/glx.h>
#define P(name, type) type name##_ = (type)glXGetProcAddress((const GLubyte*)#name)
static const char *vsrc =
    "#version 330 core\n"
    "void main(){int i=gl_VertexID;\n"
    "vec2 p=vec2(float((i<<1)&2),float(i&2));\n"
    "gl_Position=vec4(p*2.0-1.0,0.0,1.0);}";
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc, char **argv) {
    FILE *f = fopen(argv[1], "rb");
    fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
    char *src = malloc(n + 1); fread(src, 1, n, f); src[n] = 0;
    Display *dpy = XOpenDisplay(NULL);
    int attr[] = { GLX_RGBA, GLX_DOUBLEBUFFER, None };
    XVisualInfo *vi = glXChooseVisual(dpy, DefaultScreen(dpy), attr);
    GLXContext ctx = glXCreateContext(dpy, vi, NULL, True);
    Window win = XCreateSimpleWindow(dpy, DefaultRootWindow(dpy), 0, 0, 64, 64, 0, 0, 0);
    XMapWindow(dpy, win); XSync(dpy, False);
    glXMakeCurrent(dpy, win, ctx);
    P(glCreateShader, PFNGLCREATESHADERPROC);
    P(glShaderSource, PFNGLSHADERSOURCEPROC);
    P(glCompileShader, PFNGLCOMPILESHADERPROC);
    P(glCreateProgram, PFNGLCREATEPROGRAMPROC);
    P(glAttachShader, PFNGLATTACHSHADERPROC);
    P(glLinkProgram, PFNGLLINKPROGRAMPROC);
    P(glUseProgram, PFNGLUSEPROGRAMPROC);
    P(glGetProgramiv, PFNGLGETPROGRAMIVPROC);
    P(glGetProgramInfoLog, PFNGLGETPROGRAMINFOLOGPROC);
    P(glGetUniformLocation, PFNGLGETUNIFORMLOCATIONPROC);
    P(glUniform1f, PFNGLUNIFORM1FPROC);
    P(glUniform2f, PFNGLUNIFORM2FPROC);
    GLuint vs = glCreateShader_(0x8B31), fs = glCreateShader_(0x8B30);
    const char *s;
    s = vsrc; glShaderSource_(vs, 1, &s, NULL); glCompileShader_(vs);
    s = src;  glShaderSource_(fs, 1, &s, NULL); glCompileShader_(fs);
    GLuint pr = glCreateProgram_();
    glAttachShader_(pr, vs); glAttachShader_(pr, fs);
    double t0 = now(); glLinkProgram_(pr);
    GLint ok = 0, ll = 0;
    glGetProgramiv_(pr, 0x8B82 /*LINK_STATUS*/, &ok);
    glGetProgramiv_(pr, 0x8B84, &ll);
    char *log = calloc(1, ll + 1);
    glGetProgramInfoLog_(pr, ll, NULL, log);
    printf("link: %d (%.2fs)\nlog: %s\n", ok, now() - t0, log);
    if (!ok) return 1;
    glUseProgram_(pr);
    glUniform1f_(glGetUniformLocation_(pr, "iTime"), 5.0f);
    glUniform2f_(glGetUniformLocation_(pr, "iResolution"), 64.0f, 64.0f);
    glViewport(0, 0, 64, 64);
    t0 = now();
    glDrawArrays(GL_TRIANGLES, 0, 3);
    glFinish();
    printf("draw+finish: %.3fs\n", now() - t0);
    unsigned char px[4] = {0};
    glReadPixels(32, 40, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, px);
    printf("pixel(32,40): %d %d %d\n", px[0], px[1], px[2]);
    printf("glGetError: 0x%x\n", glGetError());
    return 0;
}
