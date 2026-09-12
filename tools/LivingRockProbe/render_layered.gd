extends SceneTree

const VIEW_SIZE := Vector2i(1920, 1080)
const SCREEN_RECT := Rect2(-1200.64, -675.36, 2401.28, 1350.72)

var viewport: SubViewport
var stage: Node2D

func _initialize() -> void:
	call_deferred("_render")

func _render() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1 or not ProjectSettings.load_resource_pack(args[0], true):
		push_error("usage: render_layered.gd ABSOLUTE_PCK")
		quit(1)
		return
	viewport = SubViewport.new()
	viewport.size = VIEW_SIZE
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.transparent_bg = false
	get_root().add_child(viewport)
	stage = Node2D.new()
	viewport.add_child(stage)
	_add_texture_layer("res://images/backgrounds/living_rock_generated_bg.png", -2)
	_add_texture_layer("res://images/backgrounds/living_rock_generated_ground.png", 1)
	var creature_scene := ResourceLoader.load("res://scenes/creature_visuals/living_rock.tscn", "PackedScene") as PackedScene
	if creature_scene == null:
		push_error("could not load Living Rock creature scene")
		quit(1)
		return
	var creature := creature_scene.instantiate()
	creature.position = Vector2(960, 820)
	stage.add_child(creature)
	_add_texture_layer("res://images/backgrounds/living_rock_generated_fg.png", 3)
	await _wait_frames(12)
	await _save_frame("living-rock-layered-immediate-idle.png")
	await _wait_frames(120)
	await _save_frame("living-rock-layered-idle.png")
	print("LIVING_ROCK_LAYERED_RENDER_PASS")
	quit(0)

func _add_texture_layer(path: String, z: int) -> void:
	var rect := TextureRect.new()
	rect.texture = ResourceLoader.load(path, "Texture2D")
	rect.position = SCREEN_RECT.position
	rect.size = SCREEN_RECT.size
	rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	rect.z_index = z
	stage.add_child(rect)

func _wait_frames(count: int) -> void:
	for _index in range(count):
		await process_frame

func _save_frame(name: String) -> void:
	await process_frame
	var image := viewport.get_texture().get_image()
	var output := "res://../../build/verification/living-rock-occlusion-ground-20260820-v8/" + name
	image.save_png(ProjectSettings.globalize_path(output))
