extends Node
## Independent renderer: the actual layer scenes, 23 px BgContainer offset,
## native canvas materials/particles and the game's 1920x1080 canvas contract.

var background: Control
var viewport: SubViewport
var specs: Dictionary
var out_dir := ""

func _ready() -> void:
    seed(20261003)
    specs = JSON.parse_string(FileAccess.get_file_as_string("res://scene_specs.json"))
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--capture="):
            out_dir = arg.trim_prefix("--capture=")
    if out_dir.is_empty():
        _interactive()
    else:
        call_deferred("_capture_all")

func _assemble(title: String, parent: Node, canvas_size: Vector2i) -> Control:
    var spec: Dictionary = specs[title]
    var packed := load("res://" + str(spec.root)) as PackedScene
    assert(packed != null, "Missing background root: " + title)
    var bg := packed.instantiate() as Control
    bg.position = Vector2(canvas_size) * 0.5 + Vector2(23, 0)
    parent.add_child(bg)
    for i in range(spec.layers.size()):
        var slot := "Foreground" if i == spec.layers.size() - 1 else "Layer_%02d" % i
        var layer_scene := load("res://" + str(spec.layers[i])) as PackedScene
        assert(layer_scene != null, "Missing background layer")
        bg.get_node(slot).add_child(layer_scene.instantiate())
    return bg

func _interactive() -> void:
    background = _assemble("hollow_grotto", self, Vector2i(1920, 1080))
    get_viewport().size_changed.connect(_resize)
    _resize()
    print("1-5: toggle painted planes; F: toggle cave effects; R: restore; Esc: quit")

func _resize() -> void:
    if is_instance_valid(background):
        background.position = get_viewport().get_visible_rect().size * 0.5 + Vector2(23, 0)

func _unhandled_key_input(event: InputEvent) -> void:
    if not event is InputEventKey or not event.pressed or event.echo:
        return
    if event.keycode == KEY_ESCAPE:
        get_tree().quit()
    if not is_instance_valid(background):
        return
    var names := ["Layer_00", "Layer_01", "Layer_02", "Layer_03", "Foreground"]
    if event.keycode >= KEY_1 and event.keycode <= KEY_5:
        var target := background.get_node(names[event.keycode - KEY_1]) as CanvasItem
        target.visible = not target.visible
    if event.keycode == KEY_F:
        for effect in background.get_node("Layer_01").get_child(0).get_children():
            if effect is CanvasItem and effect.name != "PaintedLayer":
                effect.visible = not effect.visible
    if event.keycode == KEY_R:
        for target in background.find_children("*", "CanvasItem", true, false):
            target.visible = true

func _new_viewport(size: Vector2i) -> void:
    viewport = SubViewport.new()
    viewport.size = size
    viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    viewport.transparent_bg = false
    add_child(viewport)

func _save(name: String) -> void:
    await RenderingServer.frame_post_draw
    var err := viewport.get_texture().get_image().save_png(out_dir.path_join(name + ".png"))
    assert(err == OK, "Capture failed: " + name)
    print("CAPTURE_PASS ", name, " ", viewport.size)

func _capture_all() -> void:
    DirAccess.make_dir_recursive_absolute(out_dir)
    for title in ["hollow_grotto", "underdocks", "overgrowth", "glory"]:
        _new_viewport(Vector2i(1920, 1080))
        var bg := _assemble(title, viewport, viewport.size)
        for i in range(60):
            await get_tree().process_frame
        await _save(title + "_native")
        if title == "hollow_grotto":
            for i in range(120):
                await get_tree().process_frame
            await _save("hollow_grotto_motion_t2")
            for effect in bg.get_node("Layer_01").get_child(0).get_children():
                if effect is CanvasItem and effect.name != "PaintedLayer":
                    effect.visible = false
            await get_tree().process_frame
            await _save("hollow_grotto_paint_only")
        viewport.queue_free()
        await get_tree().process_frame
    for size in [Vector2i(2560, 1080), Vector2i(1440, 1080)]:
        _new_viewport(size)
        _assemble("hollow_grotto", viewport, size)
        for i in range(30):
            await get_tree().process_frame
        await _save("hollow_grotto_%dx%d" % [size.x, size.y])
        viewport.queue_free()
        await get_tree().process_frame
    print("HOLLOW_GROTTO_RENDER_COMPLETE")
    get_tree().quit(0)
