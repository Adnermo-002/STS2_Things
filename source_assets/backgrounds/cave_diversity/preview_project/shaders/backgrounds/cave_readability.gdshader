shader_type canvas_item;

// Lift middle values while keeping true black and preserving texture alpha.
// Only painted background TextureRects use this material, never actors or UI.
uniform float midtone_gamma : hint_range(0.6, 1.2) = 0.82;
uniform float exposure : hint_range(0.5, 1.5) = 1.03;
varying vec4 vertex_tint;

void vertex() {
    vertex_tint = COLOR;
}

void fragment() {
    vec4 paint = texture(TEXTURE, UV);
    vec3 readable = pow(max(paint.rgb, vec3(0.0)), vec3(midtone_gamma));
    COLOR = vec4(min(readable * exposure, vec3(1.0)), paint.a) * vertex_tint;
}
