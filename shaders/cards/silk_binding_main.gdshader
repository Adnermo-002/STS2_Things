// Queen's Bound RG/A texture contract, with a local dissolve for apply/release.
shader_type canvas_item;
render_mode blend_mix;
#include "res://shaders/cards/silk_native/tiling_and_offset.gdshaderinc"
uniform vec4 bright_st = vec4(0.0, 0.0, 0.5, 0.0);
uniform float bright_energy = 1.65;
uniform float effect_amount : hint_range(0.0, 1.0) = 1.0;
varying vec4 vertex_color;
void vertex() { vertex_color = COLOR; }
void fragment() {
    vec4 bright_tex = texture(TEXTURE, tiling_and_offset(UV, bright_st, vec2(0.0)));
    vec4 main_tex = texture(TEXTURE, UV);
    float energy_multiplier = mix(1.0, bright_energy, bright_tex.g);
    float threshold = (1.0 - effect_amount) * 1.2;
    float dissolve = smoothstep(threshold - 0.15, threshold + 0.08, main_tex.g);
    COLOR = vec4(main_tex.rrr * vertex_color.rgb * energy_multiplier,
        main_tex.a * vertex_color.a * dissolve);
}
