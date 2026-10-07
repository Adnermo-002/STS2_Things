# 吸水海绵 Spine 4.2

原创皮肤为 `source_assets/monsters/water_sponge/character_final.png`，通过用户指定的 `gpt-image-2.5-sunburst` 接口模型生成，再清理透明边缘。

14 骨骼、9 动作；腹部、头、嘴、双眼、三个顶部开口、前后肢与双脚独立控制。连续蒙皮让柔软身体弯曲时保留原画，运行时视觉层按真实积水量平滑放大。

1.12.4 细化地面压缩、接触停留、回弹与部位跟随；吸水和喷淋以腹部形变传达吞水与挤水。逐帧验证新增动作结束回位和攻击蓄力／前倾方向检查。

运行 `python -m rigkit build`、`python -m rigkit export`、`python package.py`、`node verify.mjs`。只有验证通过后才用 `python package.py --deploy` 更新运行资源。

`rigkit.py`、`rigutil.py` 是现有通用工具的独立副本，修改本目录不影响血蛭等既有怪物。`pkg/verification.json` 保存官方 Spine 4.2.43 的逐帧检查。
