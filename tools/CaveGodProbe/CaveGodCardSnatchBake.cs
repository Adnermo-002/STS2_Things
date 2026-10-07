using System.Text.Json.Nodes;
using Godot;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;

public partial class CaveGodProbeNode
{
    private void BakeCardSnatch(string root, string output, MegaSprite rig)
    {
        JsonNode source = JsonNode.Parse(File.ReadAllText(Path.Combine(root, "animations/monsters/cave_god/cave_god.spjson")))!;
        JsonNode motion = JsonNode.Parse(File.ReadAllText(Path.Combine(root, "source_assets/monsters/cave_god_motion/card_snatch_motion.json")))!;
        float duration = motion["duration"]!.GetValue<float>();
        int sampleHz = motion["sample_hz"]!.GetValue<int>();
        var setup = source["bones"]!.AsArray().ToDictionary(bone => bone!["name"]!.GetValue<string>(),
            bone => bone!["rotation"]?.GetValue<float>() ?? 0);
        var clips = new JsonObject();
        GodotObject skeleton = ActionSprites[1].Call("get_skeleton").AsGodotObject();
        GodotObject state = ActionSprites[1].Call("get_animation_state").AsGodotObject();
        void Pose(string clip, float time)
        {
            state.Call("clear_tracks");
            skeleton.Call("set_to_setup_pose");
            var entry = state.Call("set_animation", clip, false, 0).AsGodotObject();
            entry.Call("set_mix_duration", 0f);
            entry.Call("set_track_time", time);
            ActionSprites[1].Call("update_skeleton", 0f);
        }
        foreach (bool right in new[] { false, true })
        foreach (bool angry in new[] { false, true })
        {
            string suffix = angry ? "_angry" : "";
            string name = "card_snatch" + (right ? "_right" : "") + suffix;
            string wrist = right ? "arm2_3" : "arm1_3";
            Pose("idle_front" + suffix, 0);
            float idleAngle = Mathf.RadToDeg(rig.GetGlobalBoneTransform(wrist)!.Value.X.Angle());
            float Mirror(float angle) => right ? 180 - angle : angle;
            (float time, float angle)[] poses = motion["wrist_angle"]!.AsArray()
                .Select(key => (key![0]!.GetValue<float>(), Mirror(key[1]!.GetValue<float>())))
                .ToArray();
            poses[0] = (0, idleAngle);
            poses[^1] = (duration, idleAngle);
            var slopes = new float[poses.Length];
            for (int i = 1; i < poses.Length - 1; i++)
            {
                if (Math.Abs(poses[i].time - motion["launch"]!.GetValue<float>()) < .00001f ||
                    Math.Abs(poses[i].time - motion["touch"]!.GetValue<float>()) < .00001f) continue;
                float before = poses[i].time - poses[i-1].time;
                float after = poses[i+1].time - poses[i].time;
                float a = (poses[i].angle - poses[i-1].angle) / before;
                float b = (poses[i+1].angle - poses[i].angle) / after;
                if (a*b > 0)
                {
                    float w1 = 2*after + before, w2 = after + 2*before;
                    slopes[i] = (w1+w2)/(w1/a+w2/b);
                }
            }
            float Desired(float time)
            {
                for (int i = 1; i < poses.Length; i++)
                {
                    if (time > poses[i].time) continue;
                    float dt = poses[i].time - poses[i-1].time;
                    float u = Mathf.Clamp((time-poses[i-1].time)/dt,0,1);
                    float u2 = u*u, u3 = u2*u;
                    return Mathf.DegToRad((2*u3-3*u2+1)*poses[i-1].angle + (u3-2*u2+u)*dt*slopes[i-1]
                        + (-2*u3+3*u2)*poses[i].angle + (u3-u2)*dt*slopes[i]);
                }
                return Mathf.DegToRad(idleAngle);
            }
            var rotations = new JsonArray();
            float? previous = null;
            var times = Enumerable.Range(0,(int)Math.Round(duration*sampleHz)+1).Select(frame => frame/(float)sampleHz)
                .Concat(poses.Select(p=>p.time)).Distinct().Order().ToArray();
            foreach (float time in times)
            {
                Pose(name,time);
                var bone = skeleton.Call("find_bone",wrist).AsGodotObject();
                for (int step = 0; step < 5; step++)
                {
                    float angle = rig.GetGlobalBoneTransform(wrist)!.Value.X.Angle();
                    float error = WrapRadians(Desired(time)-angle);
                    if (Math.Abs(error)<0.00001f) break;
                    float rotation = bone.Call("get_rotation").AsSingle();
                    bone.Call("set_rotation",rotation+0.5f);
                    skeleton.Call("update_world_transform",0);
                    float derivative = WrapRadians(rig.GetGlobalBoneTransform(wrist)!.Value.X.Angle()-angle);
                    Assert(Math.Abs(derivative)>0.00001f,"Snatch wrist solver has no rotation derivative.");
                    bone.Call("set_rotation",rotation+error/derivative*0.5f);
                    skeleton.Call("update_world_transform",0);
                }
                Assert(Math.Abs(WrapRadians(Desired(time)-rig.GetGlobalBoneTransform(wrist)!.Value.X.Angle()))<0.0002f,"Snatch wrist solve failed.");
                float value = UnwrapDegrees(bone.Call("get_rotation").AsSingle()-setup[wrist],previous);
                rotations.Add(new JsonObject { ["time"]=time, ["value"]=value });
                previous=value;
            }
            clips[name]=new JsonObject { [wrist]=rotations };
            GD.Print($"BAKE_CARD_SNATCH: {name}, {times.Length} samples, idle wrist={idleAngle:F2}deg");
        }
        File.WriteAllText(Path.Combine(output,"card_snatch_bake.json"),clips.ToJsonString(new System.Text.Json.JsonSerializerOptions { WriteIndented=true }));
    }
}
