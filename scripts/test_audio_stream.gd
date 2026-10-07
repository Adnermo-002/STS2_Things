extends SceneTree

func _initialize() -> void:
    print("Testing wav loading...")
    var stream = ResourceLoader.load("res://music/gravetide_slug/gravetide_slug_boss_theme.wav", "AudioStream")
    print("Stream loaded: ", stream)
    if stream != null:
        print("Stream type: ", stream.get_class())
        var player = AudioStreamPlayer.new()
        player.stream = stream
        root.add_child(player)
        print("Player added to root successfully")
        player.play()
        print("Player play() called successfully")
        player.queue_free()
    quit(0)
