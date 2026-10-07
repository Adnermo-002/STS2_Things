shader_type canvas_item;

uniform float water_level : hint_range(0.0, 1.0) = 0.0;
// Compatible with NCreatureVisuals.SetScaleAndHue and its temporary overlays.
uniform float h : hint_range(0.0, 1.0) = 1.0;
varying vec4 modulate_color;

void vertex() {
    modulate_color = COLOR;
}

void fragment() {
    vec4 paint = texture(TEXTURE, UV);
    // The 1280px skin sits at (2,2) in its atlas. The water follows the mesh UVs,
    // retaining the original painted pores and shadows through every Spine pose.
    vec2 skin = UV / TEXTURE_PIXEL_SIZE - vec2(2.0);
    float belly = smoothstep(0.001, 0.018, min(paint.g - paint.r, paint.b - paint.r));
    belly *= step(220.0, skin.x) * step(skin.x, 975.0);
    belly *= step(640.0, skin.y) * step(skin.y, 1160.0);
    float luma = dot(paint.rgb, vec3(0.299, 0.587, 0.114));
    vec3 dry = luma * vec3(1.70, 1.24, 0.62);
    float wave = sin(skin.x * 0.025 + TIME * 2.4) * 4.0
               + sin(skin.x * 0.047 - TIME * 1.6) * 2.0;
    float waterline = mix(1158.0, 640.0, water_level) + wave;
    float wet = smoothstep(waterline - 3.0, waterline + 3.0, skin.y);
    wet *= smoothstep(0.0, 0.025, water_level);
    vec3 water = paint.rgb * vec3(0.88, 1.15, 1.28);
    // A narrow matte edge makes the water surface readable without neon/gloss.
    float edge = (1.0 - smoothstep(2.0, 10.0, abs(skin.y - waterline))) * wet;
    water = mix(water, vec3(0.55, 0.73, 0.73), edge * 0.55);
    paint.rgb = mix(paint.rgb, mix(dry, water, wet), belly);

    mat3 rgb_to_yiq = mat3(vec3(0.2989, 0.5959, 0.2115),
                           vec3(0.5870, -0.2774, -0.5229),
                           vec3(0.1140, -0.3216, 0.3114));
    float angle = (1.0 - h) * 6.283185;
    mat3 rotation = mat3(vec3(1.0, 0.0, 0.0),
                         vec3(0.0, cos(angle), -sin(angle)),
                         vec3(0.0, sin(angle), cos(angle)));
    vec3 yiq = rgb_to_yiq * paint.rgb;
    paint.rgb = inverse(rgb_to_yiq) * (yiq * rotation);
    COLOR = paint * modulate_color;
}
