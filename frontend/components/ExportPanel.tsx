import { formats, type ExportOptions, type Project } from '../lib/api';

type Props = {
  project: Project;
  options: ExportOptions;
  locked: boolean;
  setOptions: (value: ExportOptions) => void;
  update: (value: Partial<Project>) => void;
  onUpload: (file: File | undefined, apply: (name: string) => void) => void;
  onRender: () => void;
};

export default function ExportPanel({ project, options, locked, setOptions, update, onUpload, onRender }: Props) {
  const set = (value: Partial<ExportOptions>) => setOptions({ ...options, ...value });
  return (
    <div className="panel">
      <h3>Export settings</h3>
      <fieldset disabled={locked}>
        <label>
          Format
          <select
            value={formats.findIndex((f) => f[1] === options.width && f[2] === options.height)}
            onChange={(e) => {
              const f = formats[+e.target.value];
              if (f) set({ width: f[1], height: f[2], font_size: f[1] < 500 ? 26 : 48 });
            }}
          >
            <option value="-1">Custom dimensions</option>
            {formats.map((f, i) => (
              <option key={f[0]} value={i}>
                {f[0]}
              </option>
            ))}
          </select>
        </label>
        <div className="form-grid">
          <label>
            Width
            <input type="number" step="2" value={options.width} onChange={(e) => set({ width: +e.target.value })} />
          </label>
          <label>
            Height
            <input type="number" step="2" value={options.height} onChange={(e) => set({ height: +e.target.value })} />
          </label>
        </div>
        <label>
          Fit
          <select value={options.fit} onChange={(e) => set({ fit: e.target.value })}>
            <option value="crop">Crop to fill</option>
            <option value="contain">Contain / letterbox</option>
            <option value="blur">Blurred background</option>
          </select>
        </label>
        <div className="form-grid">
          <label>
            Transition
            <select value={options.transition} onChange={(e) => set({ transition: e.target.value })}>
              <option value="fade">Fade through black</option>
              <option value="crossfade">Crossfade</option>
              <option value="none">Hard cut</option>
            </select>
          </label>
          {options.transition !== 'none' && (
            <label>
              Length (s)
              <input
                type="number"
                min="0"
                max="1.5"
                step=".05"
                value={options.fade}
                onChange={(e) => set({ fade: +e.target.value })}
              />
            </label>
          )}
        </div>
        <label className="check">
          <input type="checkbox" checked={options.captions} onChange={(e) => set({ captions: e.target.checked })} /> Burn
          in captions
        </label>
        <div className="form-grid">
          <label>
            Font size
            <input type="number" value={options.font_size} onChange={(e) => set({ font_size: +e.target.value })} />
          </label>
          <label>
            Color
            <input type="color" value={options.color} onChange={(e) => set({ color: e.target.value })} />
          </label>
        </div>
        <label>
          Characters per caption · {options.caption_chars}
          <input
            type="range"
            min="30"
            max="200"
            step="2"
            value={options.caption_chars}
            onChange={(e) => set({ caption_chars: +e.target.value })}
          />
        </label>
        <label>
          Caption position {Math.round(options.caption_y * 100)}%
          <input
            type="range"
            min=".1"
            max=".9"
            step=".01"
            value={options.caption_y}
            onChange={(e) => set({ caption_y: +e.target.value })}
          />
        </label>
        <label>
          Safe area {Math.round(options.safe_area * 100)}%
          <input
            type="range"
            min="0"
            max=".3"
            step=".01"
            value={options.safe_area}
            onChange={(e) => set({ safe_area: +e.target.value })}
          />
        </label>
        <div className="form-grid">
          {(['music', 'logo'] as const).map((key) => (
            <label key={key} className="upload-button">
              {project[key] ? 'Replace' : 'Add'} {key}
              <input
                type="file"
                accept={key === 'music' ? 'audio/*' : 'image/png,image/jpeg,image/webp'}
                onChange={(e) => onUpload(e.target.files?.[0], (name) => update({ [key]: name }))}
              />
            </label>
          ))}
        </div>
        {project.music && <button onClick={() => update({ music: '' })}>Remove music</button>}
        {project.logo && <button onClick={() => update({ logo: '' })}>Remove logo</button>}
        <label>
          Music volume · auto ducking
          <input
            type="range"
            min="0"
            max="1"
            step=".01"
            value={options.music_volume}
            onChange={(e) => set({ music_volume: +e.target.value })}
          />
        </label>
        <button className="primary full" disabled={!project.scenes.length} onClick={onRender}>
          Render MP4 ↗
        </button>
        <p className="muted small">
          H.264 · AAC · 30 fps
          <br />
          Long captions are split into timed cues. Narration can extend image scenes; video clips must be long enough.
        </p>
      </fieldset>
    </div>
  );
}
