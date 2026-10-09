extends SceneTree

# Bake the generated painting's standing plane to a straight-alpha floor PNG.
# This is export preparation; the painted content comes from image_gen.
func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	var args := OS.get_cmdline_user_args()
	var input := Image.new()
	if args.size() != 2 or input.load(args[0]) != OK:
		quit(2)
		return
	var view := SubViewport.new()
	view.size = input.get_size()
	view.transparent_bg = true
	view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	get_root().add_child(view)
	var plane := TextureRect.new()
	plane.texture = ImageTexture.create_from_image(input)
	plane.size = Vector2(view.size)
	var shader := Shader.new()
	shader.code = "shader_type canvas_item; render_mode unshaded; void fragment(){vec4 source=texture(TEXTURE,UV);COLOR=vec4(source.rgb,source.a*smoothstep(0.535,0.575,UV.y));}"
	var material := ShaderMaterial.new()
	material.shader = shader
	plane.material = material
	view.add_child(plane)
	await process_frame
	await RenderingServer.frame_post_draw
	var result := view.get_texture().get_image()
	# Viewport pixels are premultiplied; runtime imports expect straight alpha.
	for y in result.get_height():
		for x in result.get_width():
			var color := result.get_pixel(x, y)
			if color.a > 0.001 and color.a < 0.999:
				color.r /= color.a
				color.g /= color.a
				color.b /= color.a
				result.set_pixel(x, y, color)
	if result.save_png(args[1]) != OK:
		quit(3)
		return
	view.queue_free()
	await process_frame
	print("SCALE_BEETLE_FLOOR_BAKE_PASS ", input.get_size())
	quit(0)
