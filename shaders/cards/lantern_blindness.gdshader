shader_type canvas_item;
render_mode unshaded;

float noise(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

void fragment() {
    float tick = floor(TIME * 12.0);
    vec2 cell = floor(UV * vec2(62.0, 78.0));
    float n = noise(cell + vec2(tick * 3.0, tick));
    float band = noise(vec2(floor(UV.y * 22.0), tick));
    vec3 dark = vec3(0.09, 0.10, 0.19);
    vec3 violet = vec3(0.44, 0.30, 0.60);
    vec3 cyan = vec3(0.38, 0.71, 0.75);
    vec3 ink = mix(dark, violet, n * 0.8);
    ink = mix(ink, cyan, step(0.76, band) * (0.3 + 0.6 * n));
    ink += vec3(0.12, 0.08, 0.02) * step(0.92, n);
    ink *= 0.82 + 0.18 * step(0.25, fract(UV.y * 90.0));
    COLOR = vec4(ink, 1.0);
}
