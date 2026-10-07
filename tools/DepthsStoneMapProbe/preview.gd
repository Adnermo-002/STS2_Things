extends SceneTree

var workspace: String
var output: String
var package: String
var checks: int = 0

func require(condition: bool, message: String) -> void:
	if not condition:
		push_error(message)
		quit(1)
		assert(condition, message)
	checks += 1

func texture(path: String, fix_alpha_border: bool = false) -> ImageTexture:
	var source := Image.load_from_file(path)
	require(source != null and not source.is_empty(), "Load image " + path)
	if fix_alpha_border:
		# Match the PNG importer's process/fix_alpha_border setting when comparing
		# shipped textures with the uncut master; otherwise only edge RGB differs.
		source.fix_alpha_edges()
	return ImageTexture.create_from_image(source)

func _initialize() -> void:
	workspace = ProjectSettings.globalize_path("res://").path_join("../..").simplify_path()
	output = workspace.path_join("build/depths_stone_map")
	package = OS.get_environment("THINGS_MAP_PCK")
	if not OS.get_environment("THINGS_MAP_OUTPUT").is_empty():
		output = OS.get_environment("THINGS_MAP_OUTPUT")
	if not package.is_empty():
		require(ProjectSettings.load_resource_pack(package, true), "Mount shipping PCK")
	call_deferred("run_preview")

func make_rect(tex: Texture2D, dimensions: Vector2) -> TextureRect:
	var rect := TextureRect.new()
	rect.texture = tex
	rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	rect.custom_minimum_size = Vector2(0, dimensions.y)
	rect.size = dimensions
	return rect

func capture(view: SubViewport, name: String) -> void:
	await process_frame
	await process_frame
	RenderingServer.force_draw()
	var image := view.get_texture().get_image()
	require(image.save_png(output.path_join(name + ".png")) == OK, "Capture " + name)

func run_preview() -> void:
	root.size = Vector2i(1920, 1080)
	var view := SubViewport.new()
	view.size = Vector2i(1920, 3240)
	view.disable_3d = true
	view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(view)
	var backdrop := ColorRect.new()
	backdrop.color = Color("172932")
	backdrop.size = Vector2(1920, 3240)
	view.add_child(backdrop)
	var plate := VBoxContainer.new()
	plate.size = Vector2(1920, 3240)
	plate.add_theme_constant_override("separation", 0)
	view.add_child(plate)
	# Exact native NMapBg layout: three 1080-high TextureRects, no separation,
	# EXPAND_IGNORE_SIZE + KEEP_ASPECT_CENTERED. These are texture layout checks,
	# independent of a player save or the rest of NMapScreen's input services.
	for part in ["top", "middle", "bottom"]:
		var relative: String = "images/packed/map/map_bgs/depths/map_" + part + "_depths.png"
		var tex: Texture2D = texture(workspace.path_join(relative)) if package.is_empty() else load("res://" + relative)
		require(tex != null, "Load map texture " + relative)
		require(tex.get_width() == 2036 and tex.get_height() == 1440, "Native dimensions")
		var rect := make_rect(tex, Vector2(1920, 1080))
		plate.add_child(rect)
	await process_frame
	await process_frame
	for index in range(3):
		var rect := plate.get_child(index) as TextureRect
		require(is_equal_approx(rect.position.y, index * 1080.0), "Contiguous native row positions")
		require(is_equal_approx(rect.size.y, 1080.0), "Native row heights")
	await capture(view, "native_full")
	plate.visible = false
	var selected: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(workspace.path_join("source_assets/backgrounds/depths_stone_map/selection.json")))
	var master_path := workspace.path_join("source_assets/backgrounds/depths_stone_map/" + str(selected.master))
	var uncut := make_rect(texture(master_path, not package.is_empty()), Vector2(1920, 3240))
	view.add_child(uncut)
	await capture(view, "native_uncut_reference")
	uncut.queue_free()
	plate.visible = true
	await process_frame
	view.size = Vector2i(1920, 1080)
	for offset in [0, 540, 1080, 1620, 2160]:
		plate.position.y = -offset
		await capture(view, "native_scroll_" + str(offset))
	# A separate readability sample, not a fabricated gameplay screenshot.
	# Icons are extracted from the original game's atlas; the sample route is illustrative.
	var route := Node2D.new()
	view.add_child(route)
	plate.position.y = -1080
	var points: Array[Vector2] = [Vector2(740,160),Vector2(1090,165),Vector2(910,355),Vector2(665,565),Vector2(1160,560),Vector2(925,785),Vector2(730,955)]
	for connection in [[0,2],[1,2],[2,3],[2,4],[3,5],[4,5],[5,6]]:
		var a := points[connection[0]]
		var b := points[connection[1]]
		var length := a.distance_to(b)
		for distance in range(42, int(length)-35, 22):
			var dot := Sprite2D.new()
			dot.texture = texture(workspace.path_join("build/depths_stone_map/preview_icons/map_dot.png"))
			dot.position = a.lerp(b, float(distance)/length)
			dot.scale = Vector2(0.5,0.5)
			dot.modulate = Color("506E7C")
			route.add_child(dot)
	var icons := ["monster","unknown","rest","elite","shop","chest","monster"]
	for index in range(points.size()):
		var icon := Sprite2D.new()
		icon.texture = texture(workspace.path_join("build/depths_stone_map/preview_icons/map_" + icons[index] + ".png"))
		icon.position = points[index]
		icon.scale = Vector2(0.72,0.72)
		route.add_child(icon)
	await capture(view, "route_readability_sample")
	view.queue_free()
	await process_frame
	RenderingServer.force_draw()
	print("Depths stone map render: PASS (", checks, " checks)")
	quit(0)
