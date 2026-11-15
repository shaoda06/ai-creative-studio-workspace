# Viggle Remake: painted frames and the prompt

Part of [Viggle Remake](README.md): what to pass as `--ref`, `--pin` and `--prompt` (the Space and the ComfyUI node take the same three).

## Painted frames and pins

A painted frame is a frame of the source, repainted in an image editor to show the target: the new
character, the object gone, the storm rolled in. We made the ones in this repository with OpenAI's
`gpt-image`. They decide the identity and the look; the prompt and the source decide the rest.

- **`--ref`**, one to four times, takes the painted frames. The prompt calls them `<Picture 1>`, `<Picture 2>`, … in this order.
- **`--pin`** is either left out entirely or given once per `--ref`, in the same order. Each value is the source frame that ref was painted from.
  - A pinned ref is a **keyframe**: it is placed inside the output's timeline at that frame, and held there for the first four of the six steps (`--keyframe-until 0.9`).
  - It is also passed as a plain reference throughout.
  - Without `--pin`, the refs are references only: they set the look, and the model decides where it lands.
- **Pin when the clip has cuts or the painted frame's composition matters.** Pinning keeps shots on time; its cost is that the output copies the painted frame's composition at that frame.
- **One painted frame per shot is usually enough.** We add a second only where a character turns to show another side or a new one enters the shot.
- **Paint at the canvas size or the source's aspect ratio.** A pinned ref of another size is fitted to the canvas: the first one stretched, the rest cover-cropped.

## Writing the prompt

Remake reads MiniMax-H3's **six-section prompt**, in this order:

1. `subject_definitions`
2. `summary`
3. `retention_analysis`
4. `detailed_description`
5. `overall_soundscape`
6. `non_diegetic_music`

The prompt uses three kinds of label:

- `<Video 1>` is the source.
- `<Picture N>` is your N-th painted frame.
- `<Subject N>` is each thing that changes or stays.

The `detailed_description` places `[Shot N]` events at `MM:SS.mmm` timestamps, so those timestamps
must fit `--frames`. MiniMax's own writing guide is
[`docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md`](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md)
in the base repository. The ten prompts in [`examples/prompts/`](examples/prompts) are the exact
prompts behind the example clips of the same name in `examples/media/`.

Three habits matter most:

- **Write it as a description of the target video, not as an instruction.** Write "a pineapple mascot tosses the dough", not "replace the man with a pineapple".
- **Say in `retention_analysis` what changes.** That section is obeyed literally: if it says something is preserved, it is.
- **Describe each `<Subject N>` well enough to exclude everyone similar in frame.**

Every prompt we have evaluated Remake with uses this format. Free-form prompts are untested.

