shader_type canvas_item;
render_mode unshaded, blend_add;
uniform float intensity : hint_range(0.0, 1.0) = 0.08;
void fragment() {
    vec2 p = (UV - vec2(0.5)) * 2.0;
    float r = length(p);
    float theta = atan(p.y, p.x);
    float halo = exp(-r * r * mix(46.0, 7.0, intensity));
    float rays = pow(abs(cos(theta * 7.0 + 0.12)), 14.0) * exp(-r * 4.0);
    float ring = exp(-pow((r - 0.50) * 21.0, 2.0)) * 0.12;
    float a = clamp(halo * 0.75 + (rays + ring) * intensity, 0.0, 1.0) * intensity;
    COLOR = vec4(1.0, 0.69, 0.27, a);
}
