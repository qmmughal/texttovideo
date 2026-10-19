import type { Settings, Status } from '../lib/api';

export type WorkflowText = { image_workflow: string; video_workflow: string };

type Props = {
  settings: Settings;
  status: Status | null;
  workflow: WorkflowText;
  busy: boolean;
  setSettings: (value: Settings) => void;
  setWorkflow: (value: WorkflowText) => void;
  onSave: () => void;
  onRefresh: () => void;
};

export default function SettingsView({ settings, status, workflow, busy, setSettings, setWorkflow, onSave, onRefresh }: Props) {
  const set = (value: Partial<Settings>) => setSettings({ ...settings, ...value });
  const models = status?.ollama?.data?.models || [];
  const visionModels = models.filter((m) => m.capabilities?.includes('vision'));
  const voices = status?.voice?.engine === 'windows' ? status.voice.voices : [];

  return (
    <section className="settings">
      <p className="eyebrow">YOUR LOCAL ENGINE ROOM</p>
      <h1>
        Models & <em>connections.</em>
      </h1>
      <p className="muted">Install models once. Create locally, whenever inspiration strikes.</p>

      <div className="panel">
        <h3>Language & visuals</h3>
        <div className="form-grid">
          <label>
            Ollama URL
            <input value={settings.ollama} onChange={(e) => set({ ollama: e.target.value })} />
          </label>
          <label>
            ComfyUI URL
            <input value={settings.comfy} onChange={(e) => set({ comfy: e.target.value })} />
          </label>
        </div>
        <div className="form-grid">
          <label>
            Storyboard model
            <select value={settings.model} onChange={(e) => set({ model: e.target.value })}>
              <option value="">Choose a model</option>
              {models.map((m) => (
                <option key={m.name}>{m.name}</option>
              ))}
              {settings.model && !models.some((m) => m.name === settings.model) && <option>{settings.model}</option>}
            </select>
          </label>
          <label>
            Vision model (photos → story)
            <select value={settings.vision_model} onChange={(e) => set({ vision_model: e.target.value })}>
              <option value="">None</option>
              {visionModels.map((m) => (
                <option key={m.name}>{m.name}</option>
              ))}
              {settings.vision_model && !visionModels.some((m) => m.name === settings.vision_model) && (
                <option>{settings.vision_model}</option>
              )}
            </select>
          </label>
        </div>
        <p className="small muted">
          Start Ollama, then install a text model with <code>ollama pull qwen3:8b</code> and, for photo stories, a vision
          model with <code>ollama pull qwen3-vl:8b</code>. Ollama writes text only; it does not generate images or video.
          Start ComfyUI on port 8188 for visuals. Refresh connections after saving changed URLs.
        </p>
        <div className="form-grid">
          <label>
            Image engine (slideshows)
            <select value={settings.image_engine} onChange={(e) => set({ image_engine: e.target.value as Settings['image_engine'] })}>
              <option value="cpu">Built-in · runs on CPU (OpenVINO)</option>
              <option value="comfy">ComfyUI workflow</option>
            </select>
          </label>
          {settings.image_engine === 'cpu' && (
            <label>
              Run images on
              <select value={settings.cpu_image_device} onChange={(e) => set({ cpu_image_device: e.target.value })}>
                <option value="CPU">CPU</option>
                <option value="GPU">Intel graphics (GPU)</option>
                <option value="NPU">Intel NPU</option>
              </select>
            </label>
          )}
        </div>
        <p className="small muted">
          The built-in engine draws scene images without a graphics card. Download its model from Setup check. AI video
          clips always use the ComfyUI video workflow.
        </p>
        {(['image_workflow', 'video_workflow'] as const).map((key) => (
          <label key={key}>
            {key === 'image_workflow' ? 'Image' : 'Video'} workflow — ComfyUI API JSON
            <textarea
              className="code"
              rows={7}
              value={workflow[key]}
              onChange={(e) => setWorkflow({ ...workflow, [key]: e.target.value })}
            />
          </label>
        ))}
        <p className="muted small">
          Export a working workflow using ComfyUI’s API format. Replace positive prompt text with <code>{'{{prompt}}'}</code>.
          Install all required local models and nodes; use a saved image or MP4 output. Set the actual supported clip length
          below. Frame checks installed node types before submission.
        </p>
        <div className="form-grid">
          <label>
            Model clip length (seconds)
            <input
              type="number"
              min="1"
              max="30"
              value={settings.clip_seconds}
              onChange={(e) => set({ clip_seconds: +e.target.value })}
            />
          </label>
          <label>
            FFmpeg CPU threads
            <input type="number" min="1" max="16" value={settings.threads} onChange={(e) => set({ threads: +e.target.value })} />
          </label>
        </div>
      </div>

      <div className="panel">
        <h3>Captions & narration</h3>
        <label>
          Urdu-capable font path
          <input value={settings.font} onChange={(e) => set({ font: e.target.value })} />
        </label>
        <p className="muted small">
          Bundled Noto Naskh Arabic works offline. You can select another Urdu-capable font. Captions use RAQM when
          available, with local Arabic shaping and bidirectional layout as a Windows fallback.
        </p>
        <label>
          Speech model for word timing
          <select value={settings.whisper_size} onChange={(e) => set({ whisper_size: e.target.value as Settings['whisper_size'] })}>
            <option value="tiny">Tiny · fastest (75 MB)</option>
            <option value="base">Base · balanced (145 MB)</option>
            <option value="small">Small · most accurate, slower (480 MB)</option>
          </select>
        </label>
        <label>
          Narration engine
          <select value={settings.tts} onChange={(e) => set({ tts: e.target.value as Settings['tts'] })}>
            <option value="windows" disabled={status ? !status.windows : false}>
              Windows built-in voices (no install)
            </option>
            <option value="piper">Piper neural voices</option>
          </select>
        </label>
        {settings.tts === 'windows' ? (
          <div className="form-grid">
            <label>
              Voice
              <select value={settings.windows_voice} onChange={(e) => set({ windows_voice: e.target.value })}>
                <option value="">Automatic (matches project language)</option>
                {voices.map((v) => (
                  <option key={v.name} value={v.name}>
                    {v.name} · {v.language}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Speaking rate · {settings.voice_rate}
              <input
                type="range"
                min="-10"
                max="10"
                value={settings.voice_rate}
                onChange={(e) => set({ voice_rate: +e.target.value })}
              />
            </label>
          </div>
        ) : (
          <>
            <label>
              Piper executable path
              <input value={settings.piper} onChange={(e) => set({ piper: e.target.value })} />
            </label>
            <label>
              Piper ONNX voice path
              <input value={settings.voice} onChange={(e) => set({ voice: e.target.value })} />
            </label>
          </>
        )}
        <p className="muted small">
          {status?.voice?.engine === settings.tts
            ? `Detected voice: ${status?.voice?.language || 'none'}. ${status?.voice?.message}`
            : 'Save to check the selected narration engine.'}
        </p>
      </div>

      <div className="panel">
        <h3>Machine status</h3>
        <p>
          {status?.cpu || 'CPU information unavailable'} · {status?.threads || '?'} logical processors
        </p>
        <p className="muted small">
          GPU information:{' '}
          {status?.comfy?.data?.devices?.map((d) => `${d.name} (${Math.round(d.vram_total / 1024 ** 3)} GB)`).join(', ') ||
            'Connect ComfyUI to inspect available devices.'}
        </p>
        <p className="muted small">
          Video models often require substantial GPU memory. CPU-only generation may be impractical. Use a small workflow,
          short scenes, and preview resolution first.
        </p>
      </div>

      <div className="actions">
        <button disabled={busy} className="primary" onClick={onSave}>
          Save & check connections
        </button>
        <button disabled={busy} onClick={onRefresh}>
          Refresh connections
        </button>
      </div>
    </section>
  );
}
