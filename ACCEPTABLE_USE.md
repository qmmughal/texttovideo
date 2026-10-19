# Acceptable use

## Policy

Frame must not be used to create or promote hateful, abusive, discriminatory, or harmful content.

- Do not create content that targets or demeans people based on religion or belief, including hate or discrimination against any religion.
- Do not create content that promotes violence, harassment, or dehumanization.

If a request violates these rules, Frame refuses briefly and offers a safe alternative.

Respectful content about any religion or belief is welcome: devotional and festival films, history, interfaith stories, news, and personal stories about faith, doubt, or changing religion. Fiction with conflict and neutral accounts of wars or persecution are also fine. The rules are about attacking people, not about discussing religion.

## How Frame enforces it

- **Before anything is made**, a local language model reviews the request: the idea or script for a storyboard, the theme for a photo story, and the text being translated.
- **While writing**, the same rules are part of every storyboard, photo-narration, and translation prompt.
- **After writing**, the generated captions, visual prompts, and titles are reviewed before they are saved.
- **Before drawing images, voicing, or rendering**, the visual prompts and captions, including text you typed yourself, are reviewed too.

A refused request stops with a short message, for example:

> Frame can't make this: promotes hatred against a religious group. Instead, try: a film about neighbours of different faiths sharing a festival.

To limit false refusals, the reviewer must quote the offending words from your request; a refusal that does not match your text is ignored.

The review runs on your own computer with Ollama, like everything else in Frame. Nothing is sent to a cloud service, and reviewed text is not stored.

## Limits

- **Model size matters.** In our tests an 8B model (`qwen3-vl:8b`) handled every case correctly, including Urdu and Roman Urdu, while a 1B model missed some harmful requests. Frame uses the larger of your story and vision models as the reviewer, and **Setup check** warns when the reviewer is too small. You can choose a dedicated reviewer under **Models & settings → Safety reviewer**.
- **Rendering offline.** Writing, translating, and photo narration always need the reviewer. Image generation, voicing, and rendering are checked when a local model is reachable; if Ollama is not running, they continue without the check.
- **Images and uploads.** Uploaded images, video, and audio are not inspected; the rules still apply to them.
- **Open source.** Frame is MIT licensed, and anyone can modify their copy. The policy still applies to anything made with Frame, and distributing hateful or harassing content may also be illegal where you live.

## Reporting

If Frame refused something that follows these rules, or allowed something that breaks them, please [open an issue](https://github.com/qmmughal/texttovideo/issues) with the request text (or a description if it is offensive) and the model you used. Report security problems as described in [SECURITY.md](SECURITY.md).
