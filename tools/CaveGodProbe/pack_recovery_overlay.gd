extends SceneTree

func _initialize():
    var workspace = ProjectSettings.globalize_path("res://").path_join("../..").simplify_path()
    var packer = PCKPacker.new()
    var output = workspace.path_join("build/cavegod_renew/recovery-overlay.pck")
    var resource = "animations/monsters/cave_god/cave_god.spjson"
    var status = packer.pck_start(output)
    if status == OK:
        status = packer.add_file("res://" + resource, workspace.path_join(resource))
    if status == OK:
        status = packer.flush()
    print("Recovery overlay: ", error_string(status))
    quit(0 if status == OK else 1)
