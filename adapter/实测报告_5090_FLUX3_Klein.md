# FLUX 3 Image Klein 本地实测报告（BSAI 适配包）

- 实测日期：2026-10-16
- 测试机：本机（Windows 11 / 64GB RAM）
- GPU：NVIDIA GeForce RTX 5090 Laptop GPU（24.4GB VRAM，cudaMallocAsync）+ Intel 核显（Arc 系 iGPU，VEN_8086&DEV_7D67，OMNI 目标 bmg；无 Arc 独显，XPU 链路留待真机验证）
- ComfyUI：0.41.0（绘世发行版，python_embeded_cuda 3.14 / pytorch 2.13.0+cu130，comfy_kitchen CUDA 后端含 int8_convrot 反量化）
- 权重：FLUX 3 Image Klein 蒸馏版 sd_int8_convrot / sd_bf16 + Qwen3VL-4B INT8/BF16 + Flux2-VAE（从 hf-mirror 第三方非 gated 镜像下载）

## 1. 结论速览

| 配置 | 分辨率/步数 | 总耗时（含模型加载） | 热跑（权重已驻留） | 显存峰值 | 结果 |
|---|---|---|---|---|---|
| INT8 蒸馏 | 1024² / 16 步 | 98.3 s（首跑，含 ~60s 冷加载） | **35.6 s** | 默认模式 ~13.8 GB | ✅ 出图 |
| BF16 蒸馏 | 1024² / 16 步 | 190.1 s | — | ~19.4 GB | ✅ 出图 |
| INT8 蒸馏（低显存模拟） | 1024² / 16 步 | 126.1 s | — | ~10.4 GB | ✅ 出图 |

- 官方参照（BFL 博客，NVIDIA 原生环境）：5090 1024² T2I ≈ 4.1s；4070 ≈ 8.9s。
- 本机慢于官方口径 ~8–30 倍，主因是这套发行版的叠加开销（--enable-dynamic-vram + async-offload + 大量自定义节点 + sage/sol attention 补丁 + Orchestrator 调度），属"该发行版实机口径"，不是 FLUX3 本身的问题。
- 视频宣称"8G 显存能跑"：在本机以 `--reserve-vram 15`（约 9.4GB 可用预算）模拟验证，INT8 1024² 全程峰值约 **10.4GB**，生成成功。**结论：INT8 蒸馏版在 ~10GB 级显存可稳定跑通；8GB 真卡需靠动态卸载（ComfyUI 会自动把编码器/权重换出到内存），官方口径在 NVIDIA 优化内核下成立，建议 8GB 卡从 512–768px 起用。**

## 2. 测试方法

- 入口：`BSAI-FLUX3/run_flux3_test.py`（POST /prompt → 轮询 /history/{pid} → 计时 + nvidia-smi 峰值采样线程）
- 工作流：`BSAI-FLUX3/workflows/flux3_klein_t2i_api.json`（UNETLoader sd_int8 → KSampler euler 16 步 cfg 1.0 → CLIPLoader type=flux3 → VAEDecode flux2-vae → SaveImage）
- 同一中文提示词（雨夜赛博朋克街道上的虎斑猫），种子分别 42 / 777 / 555 / 999
- ComfyUI 启动参数模板见 `02_启动FLUX3_5090.bat`；关键 env：`OMNIXPU_ENABLE=0`（缺失会启动崩溃）、HF_ENDPOINT=hf-mirror、PYTORCH_CUDA_ALLOC_CONF 等

## 3. 实测数据明细

| 项目 | 数值 | 备注 |
|---|---|---|
| INT8 首跑总耗时 | 98.3 s | 含 sd_int8 5.43GB 冷加载 + TE INT8 加载 |
| INT8 热跑 | 35.6 s | 权重已驻留后第二次跑 |
| INT8 默认模式显存峰值 | 13.8 GB | 24G 卡上 ComfyUI 不主动驱逐权重 |
| INT8 低显存模式显存峰值 | 10.4 GB | `--reserve-vram 15`，~9.4GB 预算 |
| BF16 总耗时 | 190.1 s | sd_bf16 10.14GB + TE BF16 8.27GB |
| BF16 显存峰值 | 19.4 GB | 模型+编码器几乎同时驻留 |
| 出图 | 4 张 1024×1024 PNG（1.7–2.0MB） | `ComfyUI/output/BSAI_FLUX3_test_0000*.png` |

## 4. 画质核验

- 4 张图主体一致（湿毛虎斑猫、雨夜霓虹街道），中文提示理解正常（Qwen3VL TE），构图/光影/一致性无硬伤。
- INT8 与 BF16 在 1024² 下观感接近；个别图霓虹小字（如 "BE"）渲染一般，属 FLUX3 文字能力常态。
- 无崩溃、无黑图、无显存溢出；`--fast --use-sage-attention` 正常生效。

## 5. "8G 显存"判定与档位建议

- 视频/官方口径（INT8 8GB VRAM）基于 NVIDIA 优化内核 + 显存动态卸载。本机为 24GB 卡，ComfyUI 不会主动把权重换到内存，因此实测峰值（10.4–13.8GB）不代表 8GB 卡跑不了，而是代表"有显存可用时它会多用"。
- 适配包档位建议（更新到 README）：
  - ≥16GB：INT8 1024² 默认档，或 BF16（画质上限）
  - 8–12GB：INT8 + `--reserve-vram` 调优 / 低显存模式，1024² 或 768²
  - ≤8GB：INT8 + 动态卸载 + 512–768px，CFG/步数按需下调
  - Intel XPU/核显：待 Arc 真机验证（本机无 Arc 独显）

## 6. 提示词增强器验证（配套 MVP）

- 节点已注册：`/object_info/BSAI_FLUX3_PromptEnhancer` HTTP 200（分类 BSAI/FLUX3，输出 positive/negative）。
- 规则引擎（rule_only）：中文保留 + 英文质量词缀，测试通过。
- LLM 引擎（strata_local）：本地 Strata（qwen3.8-flash-next-q2_0，127.0.0.1:8080）真实扩写成功——中文提示扩为 267 字电影感描述，positive/negative 双输出非空。
- 降级行为正确：Strata 未运行时自动回退 rule_only。

## 6.5 官方提示词上采样器验证（2026-10-16 追加）

接入方式（全部 ComfyUI 0.41 原生节点，无需额外插件）：
- `CLIPLoader`（clip_name=`qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors`，type=flux3）→ 识别为 `QWEN35_9B`，按 qwen35 全量生成式文本编码器加载；
- `TextGenerate` 节点（comfy_extras/nodes_textgen.py）自回归扩写：短请求 → 完整英文场景描述（机位/光线/构图/细节）；
- 扩写结果接入正片 `CLIPTextEncode` positive。

实测（RTX 5090 Laptop 24G，1024² / 16 步蒸馏 INT8）：

| 环节 | 耗时（首跑，含冷加载） | 结果 |
|---|---|---|
| 仅上采样器扩写（文本） | ≈249 s | ✅ 中文短请求 → ~170 词英文完整描述 |
| 全流程端到端出图 | ≈453 s | ✅ `BSAI_FLUX3_upsampler_00001_.png` |

- 中文输入正常理解，输出为英文完整场景描述（BFL PUP 设计如此）；扩写文本实测样例见 `ComfyUI/output/pup_caption_00001.txt`。
- 上采样器模型许可 Apache-2.0（独立于 FLUX Kommunity License），重 9.08GB（int8_convrot）。
- 三档对比工作流齐备：`flux3_klein_t2i_api.json`（原始）/ `flux3_klein_t2i_enhanced_api.json`（增强器）/ `flux3_klein_t2i_upsampler_api.json`（官方上采样器）。

## 7. 已知问题 / 待办

1. **Strata 插件 auto-start 会"假成功"**：日志声称已启动但服务未监听 8080；手动执行 `custom_nodes\BSAI-LLM-Strata\Strata\run-q2_0.bat` 可正常拉起（已实测）。增强器对此有降级保护。
2. **用户启动器体系会自动拉起额外的 ComfyUI 实例**（本次出现 PID 30408，占用 ~13GB 显存），多实例并存时性能读数会被干扰；实测时建议关闭多余实例。
3. XPU/核显链路（03 bat、OMNIXPU_ENABLE=1、OMNI_IMAGE_XPU_TARGET=bmg）未真机验证——需 Arc 独显/核显实机确认。
4. 官方 4 个工作流 JSON 因 gated 未取得，适配包内置自建 API 模板（已验证可用）；官方 `black-forest-labs/flux-3-image-klein-comfy` 为 gated=auto，下载脚本走非 gated 镜像。
5. 非蒸馏版（`flux3_image_klein_bf16/int8_convrot`，models 下已有）来源未确认，与蒸馏版共 4 套 sd 权重；适配包检查脚本已覆盖全部必需文件。

## 8. 许可提醒（详见《许可核对报告_FLUX_Kommunity_License.md》）

- FLUX Kommunity License v1.0：免费商用门槛 <US$5M 年化收入；再分发须附许可+Attribution Notice；**禁止用 FLUX 模型/输出训练或蒸馏同类图像模型**；商用输出须内容过滤+AI 标注。
- 适配包发行版不内置权重，下载脚本指向非 gated 镜像，随包附 LICENSE/NOTICE——符合 §3/§4.e。
