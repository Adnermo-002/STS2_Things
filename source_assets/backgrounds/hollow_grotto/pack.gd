extends SceneTree
## Build only the new namespace. Vanilla scripts/VFX stay dependencies of STS2.

func _initialize() -> void:
    var args := OS.get_cmdline_user_args()
    if args.size() != 2:
        printerr("Usage: pack.gd MANIFEST_JSON OUTPUT_PCK")
        quit(2)
        return
    var entries: Array = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
    var packer := PCKPacker.new()
    var err := packer.pck_start(args[1])
    if err != OK:
        printerr("pck_start failed ", err)
        quit(3)
        return
    for entry: Dictionary in entries:
        err = packer.add_file(str(entry.resource), str(entry.file))
        if err != OK:
            printerr("Pack add failed: ", entry.resource, " ", err)
            quit(4)
            return
    err = packer.flush()
    if err != OK:
        printerr("Pack flush failed ", err)
        quit(5)
        return
    if not ProjectSettings.load_resource_pack(args[1], true):
        printerr("Pack remount failed")
        quit(6)
        return
    for entry: Dictionary in entries:
        if not FileAccess.file_exists(str(entry.resource)):
            printerr("Packed entry missing: ", entry.resource)
            quit(7)
            return
    for entry: Dictionary in entries:
        if str(entry.resource).contains("/layers/") and str(entry.resource).ends_with(".tscn"):
            var scene := ResourceLoader.load(str(entry.resource), "PackedScene", ResourceLoader.CACHE_MODE_REPLACE) as PackedScene
            if scene == null:
                printerr("Packed layer failed to load ", entry.resource)
                quit(8)
                return
            var layer := scene.instantiate()
            if not layer is Control:
                printerr("Packed layer must be Control")
                quit(9)
                return
            layer.free()
    print("PACK_ROUNDTRIP_PASS entries=", entries.size(), " output=", args[1])
    quit(0)
