import { useState } from 'react';
import { formats, type ExportOptions, type Project } from '../lib/api';

const styles = ['Cinematic', 'Documentary', 'Watercolor', '3D animation', 'Photorealistic', 'Minimal'];

const modes = [
  ['slideshow', 'Animated slideshow', 'Pan, zoom, and fade between generated or uploaded images.'],
  ['video', 'AI-generated video', 'Real clips from your configured local video workflow.'],
] as const;

type Props = {
  project: Project;
  options: ExportOptions;
  busy: boolean;
  visionModel: string;
  update: (value: Partial<Project>) => void;
  setOptions: (value: ExportOptions) => void;
  onStoryboard: () => void;
  onBlank: () => void;
  onPhotos: (files: File[]) => void;
};

export default function Wizard(props: Props) {
  const { project, options, busy, visionModel, update, setOptions } = props;
  const [source, setSource] = useState<'idea' | 'photos'>('idea');
  const [photos, setPhotos] = useState<File[]>([]);
  const fromPhotos = source === 'photos';

  return (
    <section className="wizard">
      <p className="eyebrow">01 / THE STARTING POINT</p>
      <h1>
        Every film starts
        <br />
        with <em>an idea.</em>
      </h1>
      <div className="mode-grid">
        <button className={'mode ' + (!fromPhotos ? 'chosen' : '')} onClick={() => setSource('idea')}>
          <b>From an idea or script</b>
          <p>Your Ollama model writes the storyboard. Visuals come from ComfyUI or your uploads.</p>
        </button>
        <button
          className={'mode ' + (fromPhotos ? 'chosen' : '')}
          onClick={() => {
            setSource('photos');
            update({ mode: 'slideshow' });
          }}
        >
          <b>From my photos</b>
          <p>Upload photos in order. A local vision model writes narration for each one.</p>
        </button>
      </div>
      <label>
        {fromPhotos ? 'Theme or story hint (optional)' : 'Your prompt or script'}
        <textarea
          rows={fromPhotos ? 3 : 7}
          dir="auto"
          placeholder={
            fromPhotos
              ? 'Our family trip to the northern mountains, told warmly…'
              : 'A quiet journey through the old streets of Lahore at sunrise…'
          }
          value={project.prompt}
          onChange={(e) => update({ prompt: e.target.value })}
        />
      </label>
      {fromPhotos && (
        <label className="upload-button photo-drop">
          {photos.length ? `${photos.length} photo${photos.length > 1 ? 's' : ''} selected — one scene each` : 'Choose photos'}
          <input
            type="file"
            multiple
            accept="image/png,image/jpeg,image/webp"
            onChange={(e) => setPhotos(Array.from(e.target.files || []))}
          />
        </label>
      )}
      <div className="form-grid">
        <label>
          Language
          <select value={project.language} onChange={(e) => update({ language: e.target.value })}>
            <option value="en">English</option>
            <option value="ur">اردو / Urdu</option>
          </select>
        </label>
        <label>
          {fromPhotos ? 'Narration tone' : 'Visual style'}
          <select value={project.style} onChange={(e) => update({ style: e.target.value })}>
            {styles.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Duration (seconds)
          <input
            type="number"
            min="1"
            max="3600"
            value={project.duration}
            onChange={(e) => update({ duration: +e.target.value })}
          />
        </label>
      </div>
      <div className="presets">
        {[10, 20, 30, 45, 60].map((n) => (
          <button className={project.duration === n ? 'selected' : ''} key={n} onClick={() => update({ duration: n })}>
            {n}s
          </button>
        ))}
      </div>
      <label>
        Canvas
        <select
          defaultValue="4"
          onChange={(e) => {
            const f = formats[+e.target.value];
            setOptions({ ...options, width: f[1], height: f[2], font_size: f[1] < 500 ? 26 : 48 });
          }}
        >
          {formats.map((f, i) => (
            <option key={f[0]} value={i}>
              {f[0]}
            </option>
          ))}
        </select>
      </label>
      {!fromPhotos && (
        <div className="mode-grid">
          {modes.map(([id, title, desc]) => (
            <button key={id} className={'mode ' + (project.mode === id ? 'chosen' : '')} onClick={() => update({ mode: id })}>
              <b>{title}</b>
              <p>{desc}</p>
            </button>
          ))}
        </div>
      )}
      <div className="actions">
        {fromPhotos ? (
          <button disabled={busy || !photos.length} className="primary" onClick={() => props.onPhotos(photos)}>
            {visionModel ? 'Upload & write narration →' : 'Upload photos →'}
          </button>
        ) : (
          <button disabled={busy || !project.prompt.trim()} className="primary" onClick={props.onStoryboard}>
            Generate storyboard →
          </button>
        )}
        <button disabled={busy} onClick={props.onBlank}>
          Start with a blank storyboard
        </button>
      </div>
      <small className="muted">
        {fromPhotos
          ? visionModel
            ? `Narration is written by ${visionModel} on this machine. Photos never leave your computer.`
            : 'Choose a vision model in Models & settings to write narration automatically; otherwise write captions yourself.'
          : 'Uses your selected Ollama model. No cloud API required.'}
      </small>
    </section>
  );
}
