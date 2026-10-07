shader_type canvas_item;
uniform float erosion : hint_range(0.0, 0.35) = 0.0;
varying vec2 painted_position;
void vertex() { painted_position = VERTEX; }
float grain(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void fragment() {
    vec4 paint = texture(TEXTURE, UV) * COLOR;
    float outer = smoothstep(150.0, 480.0, abs(painted_position.x));
    float lost = erosion * outer;
    if (lost > 0.0) {
        paint.a *= smoothstep(lost, lost + 0.035, grain(floor(painted_position / 10.0)));
    }
    COLOR = paint;
}
