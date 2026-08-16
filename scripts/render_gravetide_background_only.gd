extends SceneTree

const VIEWPORT_SIZE := Vector2i(1920, 1080)
const LAYERS := [
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_00_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_01_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_02_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_03_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_fg_a.tscn",
]

func _initialize() -> void:
	call_deferred("_render")

func _render() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1:
		printerr("usage: render_gravetide_background_only.gd OUTPUT_PNG")
		quit(2)
		return
	var viewport := SubViewport.new()
	viewport.size = VIEWPORT_SIZE
	viewport.transparent_bg = false
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(viewport)
	var canvas := Control.new()
	canvas.size = Vector2(VIEWPORT_SIZE)
	viewport.add_child(canvas)
	var origin := Control.new()
	origin.position = Vector2(VIEWPORT_SIZE) * 0.5
	canvas.add_child(origin)
	for path: String in LAYERS:
		var packed := load(path) as PackedScene
		if packed == null:
			printerr("failed to load background layer: %s" % path)
			quit(3)
			return
		origin.add_child(packed.instantiate())
	await process_frame
	await RenderingServer.frame_post_draw
	var error := viewport.get_texture().get_image().save_png(args[0])
	if error != OK:
		printerr("failed to save background preview: %s" % error_string(error))
		quit(4)
		return
	print("GRAVETIDE_BACKGROUND_RENDER_PASS output=%s" % args[0])
	quit(0)
