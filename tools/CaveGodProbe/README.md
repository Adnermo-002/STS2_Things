# CaveGod verification

The probe uses the installed v0.111.0 game assemblies, mutable ModelDb creatures, native Commands, hooks, intents, and move execution. It does not replace monster logic with a second simulator.

Run `scripts/verify-cavegod.ps1`. The default target is the v111 implementation. No installation or Workshop upload occurs.

Coverage includes both arms, debuff removal (including negative Strength), preserved positive buffs, three exposure windows, recovery healing, exact intent/damage agreement, 24 normal turns at A0/A10, +2/+3 growth (including repeated-break recovery), native HP scaling for 1/2/4 players, alternating capture arms, per-player trial choices, escaped/intact claws, capture interruption, Poison/Thorns defeat, native stun, phase transition and final/forced death. The pre-change DLL fails the poison-clearing assertion.

The synthetic room uses real gameplay APIs but does not start separate host/client processes. It does not establish live network/reconnect or full combat UI correctness.

`-Render` additionally mounts the game and existing mod PCK, registers shipped/mod C# scripts, loads the actual background scene with its Spine extension and renders blue/red, capture, slam and retreat frames. It checks foreground ordering on attacks and retreat. FMOD and game services are suppressed in this isolated renderer. It does not create art or replace resources.
