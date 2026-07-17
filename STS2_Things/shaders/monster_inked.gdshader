shader_type canvas_item;
render_mode blend_mix;

// Palette-preserving shared material.  The source texture owns all color
// decisions; this shader is intentionally an identity sample so runtime skeletal
// deformation cannot introduce another per-monster or global color grade.
void fragment() {
	// CanvasItem's input COLOR already contains TEXTURE * vertex/modulate color.
	// Keeping it unchanged avoids squaring both RGB and alpha.
	COLOR = COLOR;
}
