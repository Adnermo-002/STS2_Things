extends SceneTree

const CORPSE_SLUG_SKELETON := \
	"res://animations/monsters/corpse_slug/corpse_slug_skel_data.tres"
const OUTPUT_SIZE := Vector2i(720, 420)


func _initialize() -> void:
	call_deferred("_render_last_frame")


func _render_last_frame() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		push_error("Pass the destination PNG as the first user argument.")
		quit(2)
		return

	var skeleton_data := load(CORPSE_SLUG_SKELETON)
	if skeleton_data == null:
		push_error("Could not load %s" % CORPSE_SLUG_SKELETON)
		quit(3)
		return

	var viewport := SubViewport.new()
	viewport.size = OUTPUT_SIZE
	viewport.transparent_bg = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(viewport)

	var spine := SpineSprite.new()
	spine.set_skeleton_data_res(skeleton_data)
	spine.position = Vector2(OUTPUT_SIZE.x * 0.5 - 6.0, OUTPUT_SIZE.y - 99.0)
	spine.scale = Vector2.ONE * 0.46
	viewport.add_child(spine)
	var animation_state: Object = null
	for _frame in range(180):
		animation_state = spine.call("get_animation_state") as Object
		if animation_state != null:
			break
		await process_frame

	if animation_state == null:
		push_error("Corpse Slug Spine animation state did not initialize.")
		quit(4)
		return

	animation_state.call("set_animation", "die", false, 0)
	await process_frame
	var track := animation_state.call("get_current", 0) as Object
	if track == null:
		push_error("Corpse Slug die animation did not create a track.")
		quit(5)
		return

	var animation_end := float(track.call("get_animation_end"))
	# A tiny epsilon avoids a non-looping track being disposed before the pose is applied.
	track.call("set_track_time", maxf(animation_end - 0.001, 0.0))
	track.call("set_time_scale", 0.0)
	animation_state.call("update", 0.0)
	animation_state.call("apply", spine.call("get_skeleton"))

	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var image := viewport.get_texture().get_image()
	var error := image.save_png(args[0])
	if error != OK:
		push_error("Could not save Corpse Slug corpse frame: %s" % error_string(error))
		quit(6)
		return

	print("Saved Corpse Slug die frame to %s (animation_end=%.3f)" % [args[0], animation_end])
	quit()
