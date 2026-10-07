// Queen's polar noise, erosion and native card-border mask.
shader_type canvas_item;
render_mode blend_mix;
#include "res://shaders/cards/silk_native/erosion_from_factors.gdshaderinc"
#include "res://shaders/cards/silk_native/polar_coordinates.gdshaderinc"
#include "res://shaders/cards/silk_native/tiling_and_offset.gdshaderinc"
uniform vec4 main_st = vec4(1.0, 3.0, 0.25, 0.0);
uniform vec2 mask_erosion = vec2(0.4, 0.6);
uniform sampler2D mask : repeat_disable;
uniform float effect_amount : hint_range(0.0, 1.0) = 1.0;
varying vec4 vertex_color;
void vertex() { vertex_color = COLOR; }
void fragment() {
    vec2 polar_uv = polar_coordinates(UV, vec2(0.5), 1.0, 1.0);
    polar_uv = tiling_and_offset(polar_uv, main_st, vec2(0.0));
    vec4 main_tex = texture(TEXTURE, polar_uv);
    vec4 mask_tex = texture(mask, UV);
    float alpha = erosion_from_factors(mask_erosion, vertex_color.a * mask_tex.a);
    COLOR = vec4(main_tex.rgb * vertex_color.rgb, alpha * effect_amount);
}
