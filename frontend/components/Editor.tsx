import { assetUrl, isImage, newScene, type ExportOptions, type Preset, type Project, type Scene } from '../lib/api';
import ExportPanel from './ExportPanel';
import SceneCard from './SceneCard';

type Props = {
  project: Project;
  options: ExportOptions;
  preview: string;
  locked: boolean;
  dirty: boolean;
  canDescribe: boolean;
  canAlign: boolean;
  update: (value: Partial<Project>) => void;
  setOptions: (value: ExportOptions) => void;
  setPreview: (asset: string) => void;
  onSave: () => void;
  onJob: (kind: string, extra?: object) => void;
  onUpload: (file: File | undefined, apply: (name: string) => void) => void;
  presets: Preset[];
  onSavePreset: (name: string) => void;
  onDeletePreset: (preset: Preset) => void;
};

export default function Editor(props: Props) {
  const { project, options, preview, locked, dirty, canDescribe, canAlign, update, onJob, onUpload } = props;
  const total = project.scenes.reduce((sum, s) => sum + s.duration, 0);
  const photos = project.scenes.filter((s) => isImage(s.asset)).length;

  const sceneUpdate = (id: string, value: Partial<Scene>) =>
    update({ scenes: project.scenes.map((s) => (s.id === id ? { ...s, ...value } : s)) });

  const move = (index: number, offset: number) => {
    const scenes = [...project.scenes];
    [scenes[index], scenes[index + offset]] = [scenes[index + offset], scenes[index]];
    update({ scenes });
  };

  return (
    <>
      <div className="editor-heading">
        <div>
          <p className="eyebrow">02 / SHAPE YOUR STORY</p>
          <input
            className="title-input"
            disabled={locked}
            dir="auto"
            value={project.title}
            onChange={(e) => update({ title: e.target.value })}
          />
          <p className="muted">
            {project.mode === 'video' ? 'AI-generated video' : 'Animated slideshow'} · {total.toFixed(1)}s planned ·{' '}
            {project.scenes.length} scenes {dirty ? '· Unsaved changes' : ''}
          </p>
        </div>
        <button disabled={locked} onClick={props.onSave}>
          Save project
        </button>
      </div>
      <div className="editor-grid">
        <div>
          <fieldset disabled={locked}>
            <label>
              Description
              <textarea dir="auto" value={project.description} onChange={(e) => update({ description: e.target.value })} />
            </label>
            <div className="actions">
              <button onClick={() => onJob('visuals')}>✧ Generate missing visuals</button>
              {canDescribe && photos > 0 && <button onClick={() => onJob('describe')}>✎ Describe uncaptioned photos</button>}
              <button onClick={() => onJob('narration')}>♫ Generate missing voices</button>
              {canAlign && project.scenes.some((s) => s.narration && s.words_for !== s.narration) && (
                <button onClick={() => onJob('align')}>⏱ Time captions to voice</button>
              )}
              <button onClick={() => update({ scenes: [...project.scenes, newScene()] })}>＋ Scene</button>
            </div>
            {project.scenes.map((s, i) => (
              <SceneCard
                key={s.id}
                scene={s}
                index={i}
                count={project.scenes.length}
                language={project.language}
                canDescribe={canDescribe}
                onChange={(value) => sceneUpdate(s.id, value)}
                onMove={(offset) => move(i, offset)}
                onDelete={() => update({ scenes: project.scenes.filter((v) => v.id !== s.id) })}
                onUpload={onUpload}
                onJob={(kind) => onJob(kind, { scene: s.id })}
              />
            ))}
          </fieldset>
        </div>
        <div className="right-panel">
          <div className="panel">
            <div className="section-title">
              <h3>Preview</h3>
              <small>RENDERED OUTPUT</small>
            </div>
            <div className="preview" style={{ aspectRatio: `${options.width}/${options.height}`, maxHeight: 420 }}>
              {preview ? (
                <video controls src={assetUrl(preview)} />
              ) : (
                <div>
                  <span>▷</span>
                  <p>Your film is taking shape.</p>
                  <small>Render a preview to watch it here.</small>
                </div>
              )}
              <div className="safe-guide" style={{ inset: `${options.safe_area * 100}%` }} />
            </div>
            <small className="muted">Dashed guide: safe area for the next export.</small>
          </div>
          <ExportPanel
            project={project}
            options={options}
            locked={locked}
            setOptions={props.setOptions}
            update={update}
            onUpload={onUpload}
            onRender={() => onJob('render')}
            presets={props.presets}
            onSavePreset={props.onSavePreset}
            onDeletePreset={props.onDeletePreset}
          />
          {project.exports.length > 0 && (
            <div className="panel">
              <h3>Your exports</h3>
              {project.exports.map((o, i) => (
                <div className="export" key={o.asset}>
                  <button onClick={() => props.setPreview(o.asset)}>
                    ▶ {o.width} × {o.height} · {o.duration.toFixed(1)}s
                  </button>
                  <small>{o.upscaled ? 'Upscaled from source media' : 'Source media meets export resolution'}</small>
                  <a href={assetUrl(o.asset) + '?download=true'} download={`frame-${i}.mp4`}>
                    Download MP4 ↗
                  </a>{' '}
                  <a href={assetUrl(o.srt)}>SRT ↗</a>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
