extends SceneTree

func _initialize() -> void:
    ProjectSettings.load_resource_pack("D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck")
    for kind in ["flat", "add"]:
        var shader: Shader = load("res://shaders/vfx/vfx_stepped_shader_fire_%s.tres" % kind)
        var file := FileAccess.open("res://shaders/backgrounds/depths_fire_%s.gdshader" % kind, FileAccess.WRITE)
        file.store_string(shader.code)
        file.close()
    print("EXPORTED_NATIVE_FIRE_SHADERS")
    quit()
