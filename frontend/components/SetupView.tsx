import { POLICY_URL, type Job, type Settings, type Setup } from '../lib/api';

type Props = {
  setup: Setup | null;
  jobs: Job[];
  busy: boolean;
  onInstall: (kind: string, options: object) => void;
  onUse: (value: Partial<Settings>) => void;
  onCancel: (job: Job) => void;
  onRefresh: () => void;
};

type Step = {
  title: string;
  detail: string;
  ready: boolean;
  optional?: boolean;
  action?: { label: string; run: () => void; disabled?: boolean };
  job?: Job;
};

export default function SetupView({ setup, jobs, busy, onInstall, onUse, onCancel, onRefresh }: Props) {
  if (!setup) return <section className="settings"><p className="muted">Checking this computer…</p></section>;
  const { hardware: hw, plan, ollama } = setup;
  const running = jobs.find((j) => ['queued', 'running'].includes(j.status));
  const jobFor = (kind: string, match?: (j: Job) => boolean) =>
    jobs.find((j) => j.kind === kind && (!match || match(j)) && ['queued', 'running', 'failed'].includes(j.status));
  const has = (model: string) => ollama.models.some((m) => m === model || m === `${model}:latest`);
  const [textModel, textSize] = plan.text_model;
  const [visionModel, visionSize] = plan.vision_model;
  const imageModel = setup.images.models[0];
  const windowsVoices = setup.voice.engine === 'windows' ? setup.voice.voices : [];
  const english = setup.voices.catalog.find((v) => v.key === 'en_US-joe-medium');
  const urdu = setup.voices.catalog.find((v) => v.key === 'ur_PK-fasih-medium');
  const voiceJob = jobFor('voice');

  const modelStep = (role: 'text' | 'vision', model: string, size: number, chosen: string): Step => {
    const installedChoice = chosen && has(chosen);
    return {
      title: role === 'text' ? 'Story writer (language model)' : 'Photo narrator (vision model)',
      detail: installedChoice
        ? `Using ${chosen}.`
        : `Recommended for this computer: ${model} (${size} GB download).`,
      ready: !!installedChoice,
      optional: role === 'vision',
      job: jobFor('ollama_model', (j) => j.options?.model === model),
      action:
        ollama.state !== 'running'
          ? undefined
          : installedChoice
            ? undefined
            : has(model)
              ? { label: `Use ${model}`, run: () => onUse(role === 'text' ? { model } : { vision_model: model }) }
              : { label: `Install ${model}`, run: () => onInstall('ollama_model', { model, role }), disabled: !!running },
    };
  };

  const steps: Step[] = [
    {
      title: 'Ollama',
      detail:
        ollama.state === 'running'
          ? `Running · ${ollama.models.length} model${ollama.models.length === 1 ? '' : 's'} installed.`
          : ollama.state === 'installed'
            ? 'Installed but not running. Start the Ollama app, then check again.'
            : 'Not installed. Download it from ollama.com/download, install, then check again.',
      ready: ollama.state === 'running',
    },
    modelStep('text', textModel, textSize, setup.settings.model),
    modelStep('vision', visionModel, visionSize, setup.settings.vision_model),
    {
      title: 'Narration voice',
      detail: windowsVoices.length
        ? `Windows voices: ${windowsVoices.map((v) => `${v.name.replace('Microsoft ', '').replace(' Desktop', '')} (${v.language})`).join(', ')}.`
        : setup.voice.available
          ? `Piper voice ready (${setup.voice.language}).`
          : setup.voice.message,
      ready: setup.voice.available,
      job: voiceJob?.options?.key !== urdu?.key ? voiceJob : undefined,
      action:
        setup.voices.engine && english && !english.downloaded && setup.settings.tts !== 'windows'
          ? { label: `Download English voice (${english.size_mb} MB)`, run: () => onInstall('voice', { key: english.key }), disabled: !!running }
          : setup.settings.tts !== 'windows' && !setup.voice.available && windowsVoices.length
            ? { label: 'Use Windows voices', run: () => onUse({ tts: 'windows' }) }
            : undefined,
    },
    {
      title: 'Urdu narration voice',
      detail: !setup.voices.engine
        ? 'The built-in voice engine is not installed. Run setup again to add it.'
        : urdu?.downloaded
          ? `Ready · ${urdu.name} (${urdu.license} licence). Used for Urdu projects automatically.`
          : `Natural Urdu narration offline: ${urdu?.name}, about ${urdu?.size_mb} MB.`,
      ready: !!urdu?.downloaded,
      optional: true,
      job: voiceJob?.options?.key === urdu?.key ? voiceJob : undefined,
      action:
        setup.voices.engine && urdu && !urdu.downloaded
          ? { label: 'Download Urdu voice', run: () => onInstall('voice', { key: urdu.key }), disabled: !!running }
          : undefined,
    },
    {
      title: 'Content safety',
      detail: !setup.safety.model
        ? 'Install a story writer model; it also checks requests against the acceptable-use policy.'
        : setup.safety.small
          ? `${setup.safety.model} reviews requests, but models this small miss some harmful ones. Install a 4B or larger model, or choose one as the safety reviewer in Models & settings.`
          : `${setup.safety.model} checks every request against the acceptable-use policy before anything is made.`,
      ready: !!setup.safety.model && !setup.safety.small,
      optional: true,
    },
    {
      title: 'AI images on this computer',
      detail: !setup.images.openvino
        ? 'The OpenVINO image engine is not installed. Run setup again to add it.'
        : imageModel?.downloaded
          ? setup.images.engine === 'cpu'
            ? `Ready · ${imageModel.name}. Runs on ${hw.openvino_devices.includes('GPU') ? 'CPU or Intel graphics' : 'the CPU'}.`
            : `${imageModel.name} is downloaded but ${setup.images.comfy ? 'ComfyUI' : 'another engine'} is selected.`
          : plan.images === 'comfy'
            ? 'Your graphics card can use ComfyUI instead; the built-in engine is a simpler alternative.'
            : `Draw scene pictures without a graphics card. ${imageModel?.name} (${imageModel?.size_gb} GB, ${imageModel?.license} licence).`,
      ready: !!imageModel?.downloaded && setup.images.engine === 'cpu',
      optional: plan.images === 'comfy',
      job: jobFor('image_model'),
      action: !setup.images.openvino
        ? undefined
        : !imageModel?.downloaded
          ? { label: `Download (${imageModel?.size_gb} GB)`, run: () => onInstall('image_model', { key: imageModel.key }), disabled: !!running }
          : setup.images.engine !== 'cpu'
            ? { label: 'Use built-in images', run: () => onUse({ image_engine: 'cpu' }) }
            : undefined,
    },
    {
      title: 'Word-synced captions',
      detail: !setup.words.whisper
        ? 'Speech timing is not installed. Run setup again to add it. Windows voices still give exact word timing.'
        : setup.words.downloaded
          ? `Ready · the ${setup.words.size} speech model times uploaded and Piper narration word by word.`
          : `Windows voices already give exact word timing. For uploaded or Piper narration, add the ${setup.words.size} speech model (about 150 MB).`,
      ready: setup.words.whisper && setup.words.downloaded,
      optional: true,
      job: jobFor('whisper_model'),
      action:
        setup.words.whisper && !setup.words.downloaded
          ? { label: 'Download speech model', run: () => onInstall('whisper_model', {}), disabled: !!running }
          : undefined,
    },
  ];
  const required = steps.filter((s) => !s.optional);
  const done = required.filter((s) => s.ready).length;

  return (
    <section className="settings">
      <p className="eyebrow">FIRST RUN</p>
      <h1>
        Setup <em>check.</em>
      </h1>
      <p className="muted">
        {done === required.length
          ? 'Everything essential is ready. Optional extras are below.'
          : `${done} of ${required.length} essentials ready. Each step downloads only what this computer can run well.`}
      </p>
      <div className="panel machine">
        <div>
          <h3>This computer</h3>
          <p>
            {hw.ram_gb} GB memory · {hw.threads} CPU threads · {hw.disk_free_gb} GB free
          </p>
          <p className="muted small">
            {hw.nvidia.length
              ? hw.nvidia.map((g) => `${g.name} (${g.vram_gb} GB)`).join(', ')
              : 'No NVIDIA graphics card found. Everything below runs on the CPU.'}
          </p>
        </div>
        <div className="plan">
          <span className="pill">{plan.name}</span>
          <p className="small">{plan.summary}</p>
          {!plan.video && (
            <p className="small muted">
              AI video clips need an NVIDIA card with 8 GB or more. Animated slideshows work on every computer.
            </p>
          )}
        </div>
      </div>
      {steps.map((step) => (
        <div className="panel step" key={step.title}>
          <span className={'status ' + (step.ready ? 'ok' : step.optional ? 'optional' : 'todo')}>
            {step.ready ? '✓' : step.optional ? '○' : '!'}
          </span>
          <div className="step-body">
            <b>
              {step.title}
              {step.optional && !step.ready && <small> · optional</small>}
            </b>
            <p className="small muted">{step.detail}</p>
            {step.job && (
              <div className="step-job">
                <p className="small">{step.job.stage}</p>
                {step.job.status !== 'failed' && <progress max="100" value={step.job.progress} />}
              </div>
            )}
          </div>
          {step.job && ['queued', 'running'].includes(step.job.status) ? (
            <button onClick={() => onCancel(step.job!)}>Cancel</button>
          ) : (
            step.action && (
              <button className="primary" disabled={busy || step.action.disabled} onClick={step.action.run}>
                {step.action.label}
              </button>
            )
          )}
        </div>
      ))}
      <div className="actions">
        <button disabled={busy} onClick={onRefresh}>
          Check again
        </button>
      </div>
      <p className="small muted">
        Frame refuses hateful, abusive, discriminatory, or harmful content. Read the{' '}
        <a href={POLICY_URL} target="_blank" rel="noreferrer">
          acceptable-use policy
        </a>
        .
      </p>
    </section>
  );
}
