extends Node

const ORDER := ["hollow_grotto_moss", "hollow_grotto_ember", "hollow_grotto_violet", "hollow_grotto"]
var specs: Dictionary
var background: Control
var viewport: SubViewport
var caption: Label
var selected := 0
var out_dir := ""

func _ready() -> void:
    seed(20261003)
    specs = JSON.parse_string(FileAccess.get_file_as_string("res://scene_specs.json"))
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--capture="):
            out_dir = arg.trim_prefix("--capture=")
    if not out_dir.is_empty():
        call_deferred("_capture_all")
        return
    var ui := CanvasLayer.new()
    add_child(ui)
    caption = Label.new()
    caption.position = Vector2(24, 28)
    caption.add_theme_font_size_override("font_size", 23)
    ui.add_child(caption)
    _show_variant(0)
    get_viewport().size_changed.connect(_resize)

func _assemble(title: String, parent: Node, canvas_size: Vector2i) -> Control:
    var spec: Dictionary = specs[title]
    var packed := load("res://" + str(spec.root)) as PackedScene
    assert(packed != null, "Missing background root " + title)
    var bg := packed.instantiate() as Control
    bg.position = Vector2(canvas_size) * 0.5 + Vector2(23, 0)
    parent.add_child(bg)
    for i in range(spec.layers.size()):
        var slot := "Foreground" if i == spec.layers.size() - 1 else "Layer_%02d" % i
        var layer := load("res://" + str(spec.layers[i])) as PackedScene
        assert(layer != null, "Missing cave layer")
        bg.get_node(slot).add_child(layer.instantiate())
    return bg

func _show_variant(index: int) -> void:
    selected = wrapi(index, 0, ORDER.size())
    if is_instance_valid(background):
        remove_child(background)
        background.queue_free()
    background = _assemble(ORDER[selected], self, Vector2i(get_viewport().get_visible_rect().size))
    caption.text = str(specs[ORDER[selected]].name) + "    |    1 / 2 / 3 / 4  ·  ← →  ·  F: effects  ·  Esc"
    print("PREVIEW_VARIANT ", ORDER[selected])

func _resize() -> void:
    if is_instance_valid(background):
        background.position = get_viewport().get_visible_rect().size * 0.5 + Vector2(23, 0)

func _unhandled_key_input(event: InputEvent) -> void:
    if not event is InputEventKey or not event.pressed or event.echo:
        return
    if event.keycode == KEY_ESCAPE:
        get_tree().quit()
    elif event.keycode >= KEY_1 and event.keycode <= KEY_4:
        _show_variant(event.keycode - KEY_1)
    elif event.keycode == KEY_RIGHT:
        _show_variant(selected + 1)
    elif event.keycode == KEY_LEFT:
        _show_variant(selected - 1)
    elif event.keycode == KEY_F:
        for effect in background.get_node("Layer_01").get_child(0).get_children():
            if effect is CanvasItem and effect.name != "PaintedLayer":
                effect.visible = not effect.visible

func _make_viewport(size: Vector2i) -> void:
    viewport = SubViewport.new()
    viewport.size = size
    viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    add_child(viewport)

func _save(name: String) -> void:
    await RenderingServer.frame_post_draw
    var err := viewport.get_texture().get_image().save_png(out_dir.path_join(name + ".png"))
    assert(err == OK, "Failed capture " + name)
    print("CAPTURE_PASS ", name, " ", viewport.size)

func _capture_all() -> void:
    DirAccess.make_dir_recursive_absolute(out_dir)
    for title in ORDER:
        _make_viewport(Vector2i(1920, 1080))
        _assemble(title, viewport, viewport.size)
        for i in range(60):
            await get_tree().process_frame
        await _save(title)
        for i in range(120):
            await get_tree().process_frame
        await _save(title + "_t2")
        viewport.queue_free()
        await get_tree().process_frame
        for size in [Vector2i(2560, 1080), Vector2i(1440, 1080)]:
            _make_viewport(size)
            _assemble(title, viewport, size)
            for i in range(30):
                await get_tree().process_frame
            await _save(title + "_%dx%d" % [size.x, size.y])
            viewport.queue_free()
            await get_tree().process_frame
    print("CAVE_VARIANTS_RENDER_COMPLETE")
    get_tree().quit(0)
