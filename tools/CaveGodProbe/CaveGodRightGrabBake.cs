using System.Text.Json.Nodes;
using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;

public partial class CaveGodProbeNode
{
    private void BakeRightGrab(string root, string output, MegaSprite rig)
    {
        JsonNode source = JsonNode.Parse(File.ReadAllText(Path.Combine(root, "animations/monsters/cave_god/cave_god.spjson")))!;
        var setup = source["bones"]!.AsArray().ToDictionary(bone => bone!["name"]!.GetValue<string>(),
            bone => bone!["rotation"]?.GetValue<float>() ?? 0);
        var clips = new JsonObject();
        GodotObject skeleton = ActionSprites[1].Call("get_skeleton").AsGodotObject();
        GodotObject state = ActionSprites[1].Call("get_animation_state").AsGodotObject();
        void Pose(string clip, float time, bool useIk)
        {
            state.Call("clear_tracks");
            skeleton.Call("set_to_setup_pose");
            using var variant = state.Call("set_animation", clip, false, 0);
            var entry = variant.AsGodotObject();
            entry.Call("set_mix_duration", 0f);
            entry.Call("set_track_time", time);
            ActionSprites[1].Call("update_skeleton", 0f);
            if (useIk)
            {
                foreach (string name in new[] { "arm1_IK", "arm2_IK" })
                {
                    var constraint = skeleton.Call("find_ik_constraint", name).AsGodotObject();
                    constraint.Call("set_mix", 1f);
                    constraint.Call("set_bend_direction", name == "arm1_IK" ? -1 : 1);
                }
                skeleton.Call("update_world_transform", 0);
            }
        }
        float Solve(string boneName, float target)
        {
            GodotObject bone = skeleton.Call("find_bone", boneName).AsGodotObject();
            for (int iteration = 0; iteration < 5; iteration++)
            {
                float angle = rig.GetGlobalBoneTransform(boneName)!.Value.X.Angle();
                float error = WrapRadians(target - angle);
                if (Math.Abs(error) < 0.00001f) break;
                float rotation = bone.Call("get_rotation").AsSingle();
                bone.Call("set_rotation", rotation + 0.5f);
                skeleton.Call("update_world_transform", 0);
                float step = WrapRadians(rig.GetGlobalBoneTransform(boneName)!.Value.X.Angle() - angle);
                Assert(Math.Abs(step) > 0.00001f, "Wrist rotation cannot be solved.");
                bone.Call("set_rotation", rotation + error / step * 0.5f);
                skeleton.Call("update_world_transform", 0);
            }
            Assert(Math.Abs(WrapRadians(target - rig.GetGlobalBoneTransform(boneName)!.Value.X.Angle())) < 0.0002f,
                "Wrist rotation solver did not converge.");
            return bone.Call("get_rotation").AsSingle() - setup[boneName];
        }
        foreach (bool angry in new[] { false, true })
        foreach (string baseName in new[] { "grab_player", "grab_slam" })
        {
            string suffix = angry ? "_angry" : "";
            string left = baseName + suffix;
            string right = baseName + "_right" + suffix;
            float duration = baseName == "grab_player" ? 5f : 1.7f;
            var rightWrist = new JsonArray();
            var leftWrist = new JsonArray();
            float? previousRight = null, previousLeft = null;
            int count = (int)Math.Round(duration * 60);
            for (int frame = 0; frame <= count; frame++)
            {
                float time = frame == count ? duration : frame / 60f;
                Pose(left, time, useIk: false);
                float desiredRight = MathF.PI - rig.GetGlobalBoneTransform("arm1_3")!.Value.X.Angle();
                float desiredLeft = MathF.PI - rig.GetGlobalBoneTransform("arm2_3")!.Value.X.Angle();
                Pose(right, time, useIk: true);
                float rightValue = UnwrapDegrees(Solve("arm2_3", desiredRight), previousRight);
                float leftValue = UnwrapDegrees(Solve("arm1_3", desiredLeft), previousLeft);
                rightWrist.Add(new JsonObject { ["time"] = time, ["value"] = rightValue });
                leftWrist.Add(new JsonObject { ["time"] = time, ["value"] = leftValue });
                previousRight = rightValue;
                previousLeft = leftValue;
            }
            clips[right] = new JsonObject { ["arm1_3"] = leftWrist, ["arm2_3"] = rightWrist };
            GD.Print($"BAKE_RIGHT_GRAB: {right}, {count + 1} samples, continuous wrist rotations");
        }
        File.WriteAllText(Path.Combine(output, "right_grab_bake.json"), clips.ToJsonString(new System.Text.Json.JsonSerializerOptions { WriteIndented = true }));
    }

    private static float WrapRadians(float value) => MathF.Atan2(MathF.Sin(value), MathF.Cos(value));
    private static float UnwrapDegrees(float value, float? previous) => previous is { } last
        ? last + Mathf.RadToDeg(WrapRadians(Mathf.DegToRad(value - last))) : value;
}
