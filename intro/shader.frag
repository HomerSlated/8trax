#version 330 core

// Uniforms set each frame by about.asm
uniform float iTime;
uniform vec2  iResolution;

out vec4 fragColor;

// ── SDF primitives ────────────────────────────────────────────────────────────

float sdSphere(vec3 p, float r) {
    return length(p) - r;
}

// ── Scene ─────────────────────────────────────────────────────────────────────

float scene(vec3 p) {
    // Infinite grid of spheres via domain repetition
    vec3 q = mod(p + 2.0, 4.0) - 2.0;
    return sdSphere(q, 0.5);
}

// ── Normal via central differences ────────────────────────────────────────────

vec3 calcNormal(vec3 p) {
    const vec2 e = vec2(0.001, 0.0);
    return normalize(vec3(
        scene(p + e.xyy) - scene(p - e.xyy),
        scene(p + e.yxy) - scene(p - e.yxy),
        scene(p + e.yyx) - scene(p - e.yyx)
    ));
}

// ── Main ──────────────────────────────────────────────────────────────────────

void main() {
    vec2 uv = (gl_FragCoord.xy - 0.5 * iResolution) / iResolution.y;

    // Camera flies forward along Z
    vec3 ro = vec3(0.0, 0.2, iTime * 0.5);
    vec3 rd = normalize(vec3(uv, 1.3));

    // Sphere-trace the scene
    float t = 0.0;
    for (int i = 0; i < 80; i++) {
        float d = scene(ro + rd * t);
        if (d < 0.0005 || t > 50.0) break;
        t += d;
    }

    // Shade
    vec3 col = vec3(0.04, 0.0, 0.08);   // deep purple background
    if (t < 50.0) {
        vec3 p    = ro + rd * t;
        vec3 n    = calcNormal(p);
        vec3 ld   = normalize(vec3(0.5, 1.0, -0.3));
        float diff = clamp(dot(n, ld), 0.0, 1.0);
        float spec = pow(clamp(dot(reflect(-ld, n), -rd), 0.0, 1.0), 32.0);
        col = vec3(0.1, 0.04, 0.35) * diff
            + vec3(0.9, 0.7, 1.0)   * spec * 0.6;
    }

    // Fade in over first 2.5 seconds
    col *= smoothstep(0.0, 2.5, iTime);

    fragColor = vec4(col, 1.0);
}
