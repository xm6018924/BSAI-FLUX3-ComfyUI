---
language:
- en
license: other
license_name: flux-kommunity-license
license_link: LICENSE.md
pipeline_tag: image-to-image
tags:
- comfyui
- diffusion-single-file
- image-generation
- image-editing
- flux
- flux-3
- black-forest-labs
base_model:
- black-forest-labs/flux-3-image-klein
- black-forest-labs/flux-3-image-klein-base
- black-forest-labs/flux-3-image-klein-pup
---
> Ungated mirror of [black-forest-labs/flux-3-image-klein-comfy](https://huggingface.co/black-forest-labs/flux-3-image-klein-comfy). All credit to Black Forest Labs. This is not an official Black Forest Labs release. The model is licensed under the FLUX Kommunity License (non-commercial), included here as `LICENSE.md` with `NOTICE.md`; any rights to use it are granted directly by Black Forest Labs under that license.

# FLUX 3 Image Klein for ComfyUI

![Launch gallery](./launch-gallery.jpg)

FLUX 3 Image Klein is a 5.6B open weights model for text-to-image generation and image editing. It takes a prompt and up to 10 reference images and returns one image. Text-to-image, single-reference edits and multi-reference compositions run through the same model, with Qwen3-VL-4B-Instruct as the text encoder.

The 5.6B parameter label refers to the image transformer; the text encoder is separate.

This repository holds the model files repackaged for [ComfyUI](https://github.com/comfyanonymous/ComfyUI): the distilled and base transformers in BF16, int8 and NVFP4, the text encoder in BF16 and int8, the prompt upsampler in int8, and the image autoencoder. The original model repositories are [FLUX 3 Image Klein](https://huggingface.co/black-forest-labs/flux-3-image-klein), [FLUX 3 Image Klein Base](https://huggingface.co/black-forest-labs/flux-3-image-klein-base) and [FLUX 3 Image Klein Prompt Upsampler](https://huggingface.co/black-forest-labs/flux-3-image-klein-pup).

Inference code, prompt upsampling and the bounding box format: [black-forest-labs/flux-3-image-klein](https://github.com/black-forest-labs/flux-3-image-klein) on GitHub.

| Checkpoint | Format | Steps | Guidance | Built for |
| --- | --- | --- | --- | --- |
| [Klein Base](https://huggingface.co/black-forest-labs/flux-3-image-klein-base) | undistilled, bfloat16 | 50 | 3.5 | fine-tuning, LoRA training, research |
| [Klein](https://huggingface.co/black-forest-labs/flux-3-image-klein) | distilled, bfloat16 | 16 | none | generation and editing, self-hosting; the checkpoint behind the BFL API |

## Key Features

1. Text-to-image, single-reference editing and multi-reference generation in one model.
2. Bounding boxes in the prompt. Place elements with boxes on a 0 to 1000 grid, then recolor, move, replace or remove them through the prompt. Boxes guide placement and scale; they do not constrain pixels to a hard mask.
3. Text rendering within generated images.
4. Released under the [FLUX Kommunity License](LICENSE.md). The license permits non-commercial use and provides a commercial-output exception for Qualifying Users, subject to its terms. See [License](#license) below.

## Files

Place the files in the following folders:

```
📂 ComfyUI/
└── 📂 models/
    ├── 📂 diffusion_models/
    │   ├── flux3_image_klein_bf16.safetensors
    │   ├── flux3_image_klein_int8_convrot.safetensors
    │   ├── flux3_image_klein_nvfp4.safetensors
    │   ├── flux3_image_klein_sd_bf16.safetensors
    │   ├── flux3_image_klein_sd_int8_convrot.safetensors
    │   └── flux3_image_klein_sd_nvfp4.safetensors
    ├── 📂 text_encoders/
    │   ├── qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors
    │   ├── qwen3vl_4b_bf16.safetensors
    │   └── qwen3vl_4b_int8_convrot.safetensors
    └── 📂 vae/
        └── flux2-vae.safetensors
```

Files with `_sd_` in the name are the distilled checkpoint; the others are the base checkpoint.

| File | Content | Size |
| --- | --- | --- |
| `diffusion_models/flux3_image_klein_sd_bf16.safetensors` | Klein, distilled, BF16 | 11.1 GB |
| `diffusion_models/flux3_image_klein_sd_int8_convrot.safetensors` | Klein, distilled, int8 | 5.8 GB |
| `diffusion_models/flux3_image_klein_sd_nvfp4.safetensors` | Klein, distilled, NVFP4 | 5.3 GB |
| `diffusion_models/flux3_image_klein_bf16.safetensors` | Klein Base, BF16 | 11.1 GB |
| `diffusion_models/flux3_image_klein_int8_convrot.safetensors` | Klein Base, int8 | 5.8 GB |
| `diffusion_models/flux3_image_klein_nvfp4.safetensors` | Klein Base, NVFP4 | 5.3 GB |
| `text_encoders/qwen3vl_4b_bf16.safetensors` | Qwen3-VL-4B-Instruct text encoder, BF16 | 8.9 GB |
| `text_encoders/qwen3vl_4b_int8_convrot.safetensors` | Qwen3-VL-4B-Instruct text encoder, int8 | 4.9 GB |
| `text_encoders/qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors` | prompt upsampler, int8 | 9.8 GB |
| `vae/flux2-vae.safetensors` | image autoencoder | 0.3 GB |

The BF16 transformer and the autoencoder are the same files as `model.safetensors` and `ae.safetensors` on the original repositories. The int8 files run on 8 GB GPUs such as the RTX 3070, and on GPUs without FP8 support (RTX 30 series and older). NVFP4 needs a Blackwell GPU.

## Download

One checkpoint, its text encoder and the autoencoder, straight into the ComfyUI model folders:

```sh
hf download black-forest-labs/flux-3-image-klein-comfy \
  diffusion_models/flux3_image_klein_sd_int8_convrot.safetensors \
  text_encoders/qwen3vl_4b_int8_convrot.safetensors \
  vae/flux2-vae.safetensors \
  --local-dir ComfyUI/models
```

Swap the first two file names for the precision and checkpoint you want from the table above. Add `text_encoders/qwen3.5_9b_flux3_prompt_upsampler_int8_convrot.safetensors` to run the prompt upsampler, which rewrites a short request into the full scene caption before generation.

## Using with ComfyUI

Sample with the defaults of the checkpoint: 16 steps and no guidance for the distilled checkpoint, 50 steps and CFG 3.5 for the base checkpoint. For editing, pass up to 10 reference images with the prompt.

[TO CONFIRM: Stephen: the ComfyUI version that supports FLUX 3 Image Klein and the workflow template links (text-to-image, editing, prompt upsampler); the public ComfyUI tree has no FLUX 3 Image loader yet.]

## Prompting
The caption controls composition; reference images anchor content, they do not lock structure.
- Write full scene captions: framing, subject, background, lighting. A short prompt gives generic output, and a one-line edit instruction ("make it blue") reframes the shot. The prompt upsampler writes the caption from a short request.
- For edits, describe the target image as a complete caption of the reference with the edit folded in, or let the prompt upsampler write it from the instruction and the references. For style, describe the attributes (palette, stroke, texture) rather than naming an artwork.
- For layout, append a JSON list of elements to the caption. Each box is `[top, left, bottom, right]` on a 0 to 1000 grid; tag the element in the caption with `<id>`:
```text
Minimalist graphic illustration featuring a black silhouette of a person <silhouette_1> centered against a solid, vibrant chartreuse background <background_1>. The figure is captured in a dynamic, mid-stride running pose, facing toward the left side of the frame. [{"id": "background_1", "bbox": [0, 0, 1000, 1000], "desc": "A flat field of neon yellow-green with a subtle paper texture and fine, organic grain."}, {"id": "silhouette_1", "bbox": [150, 150, 850, 850], "desc": "A black silhouette of a person in motion, made of dense stippled ink."}]
```
For edits by box, refer to the n-th reference as `<ref_image_n>` and give each element `from`, `src_bbox` and `tgt_bbox`; a `null` target removes it. The full format with worked examples: [Bounding boxes](https://docs.bfl.ai/flux_3/flux3_image_bounding_boxes).

## Limitations

- This model is not intended or able to provide factual information.
- While the model can output text, text rendered may be inaccurate or subject to distortion.
- As a statistical model, this checkpoint may represent or amplify biases observed in the training data.
- The model may fail to generate output that matches the prompts.
- Prompt following is heavily influenced by the prompting style. Short prompts produce generic output.
- Boxes set placement and scale, not a hard mask: an element can extend past its box, and small requested elements may not appear. Edits can change content outside the requested region.

## Out-of-scope use

See Section 4 of the [FLUX Kommunity License](LICENSE.md) for the full restrictions. They include military purposes; surveillance, including related research and development; biometric processing; unlawful, unsafe, fraudulent, defamatory, or abusive activity; generating unlawful content, including child sexual abuse material or non-consensual intimate images; violating third-party rights, including rights of publicity or digital replica rights; and using the model, its Derivatives, or its Outputs to improve another AI model that performs a function similar to a FLUX Model or Derivative.

The license also covers export controls and sanctions. Its commercial-use exception is not blanket permission for commercial fine-tuning or distribution. Consult the full license for the terms that apply to each use.

Nothing contained in this model card should be interpreted as or deemed a restriction or modification to the license the model is released under.

## Responsible AI Development

Black Forest Labs is committed to responsible model development and deployment. Prior to releasing FLUX 3 Image Klein, we evaluated and mitigated a number of risks, including child sexual abuse material (CSAM) and nonconsensual intimate imagery (NCII). For detailed information about our mitigations, evaluation processes, content provenance features, and policies, please see our post: [Capable, Open, and Safe: Combating AI Misuse](https://bfl.ai/blog/capable-open-and-safe-combating-ai-misuse). 
To report safety concerns, contact [safety@blackforestlabs.ai](mailto:safety@blackforestlabs.ai).

## License

This model is released under the [FLUX Kommunity License v.1.0](LICENSE.md): non-commercial use, plus commercial output generation by Qualifying Users with less than US$5M in gross annualized revenue, including affiliates, subject to the license terms. For other uses, see [commercial licensing](https://bfl.ai/licensing).

The Qwen3-VL-4B-Instruct text encoder is under [Apache-2.0](https://huggingface.co/black-forest-labs/flux-3-image-klein/blob/main/text_encoder/LICENSE). The prompt upsampler is under [Apache-2.0](https://huggingface.co/black-forest-labs/flux-3-image-klein-pup).

## Trademarks and IP

Use of Black Forest Labs and FLUX trademarks requires prior written permission, except for required attribution or necessary descriptive references. Use must not cause confusion or imply sponsorship or endorsement. Third-party trademarks remain subject to their owners' policies.

## Citation

If you use FLUX 3 Image in your work, please cite:

```bibtex
@misc{bfl2026flux3image,
  author       = {{Black Forest Labs}},
  title        = {{FLUX} 3 Image Klein},
  year         = {2026},
  url          = {https://bfl.ai/blog/flux-3-image-klein},
}