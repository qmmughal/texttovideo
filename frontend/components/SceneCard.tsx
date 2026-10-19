import { assetUrl, isImage, motions, type Motion, type Scene } from '../lib/api';

type Props = {
  scene: Scene;
  index: number;
  count: number;
  language: string;
  canDescribe: boolean;
  onChange: (value: Partial<Scene>) => void;
  onMove: (offset: number) => void;
  onDelete: () => void;
  onUpload: (file: File | undefined, apply: (name: string) => void) => void;
  onJob: (kind: string) => void;
};

export default function SceneCard({ scene, index, count, language, canDescribe, onChange, onMove, onDelete, onUpload, onJob }: Props) {
  const image = isImage(scene.asset);
  return (
    <article className="scene">
      <div className="scene-top">
        <b>
          <span>{String(index + 1).padStart(2, '0')}</span> SCENE
        </b>
        <div>
          <button aria-label="Move scene up" disabled={index === 0} onClick={() => onMove(-1)}>
            ↑
          </button>
          <button aria-label="Move scene down" disabled={index === count - 1} onClick={() => onMove(1)}>
            ↓
          </button>
          <button aria-label="Delete scene" onClick={onDelete}>
            ×
          </button>
        </div>
      </div>
      <div className="scene-content">
        <div className="scene-media">
          {scene.asset ? (
            image ? (
              <img src={assetUrl(scene.asset)} alt={`Scene ${index + 1}`} />
            ) : (
              <video controls src={assetUrl(scene.asset)} />
            )
          ) : (
            <div className="empty-visual">
              ◇<small>Your visual goes here</small>
            </div>
          )}
          <label className="upload-button">
            Upload visual
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp,video/mp4,video/webm,video/quicktime"
              onChange={(e) => onUpload(e.target.files?.[0], (asset) => onChange({ asset }))}
            />
          </label>
          <button onClick={() => onJob('visuals')}>Regenerate visual</button>
          {image && canDescribe && <button onClick={() => onJob('describe')}>✎ Describe photo</button>}
        </div>
        <div className="scene-fields">
          <label>
            Script & caption
            <textarea
              dir={language === 'ur' ? 'rtl' : 'ltr'}
              lang={language}
              rows={3}
              value={scene.text}
              onChange={(e) => onChange({ text: e.target.value })}
            />
          </label>
          <label>
            Visual prompt
            <textarea rows={2} value={scene.prompt} onChange={(e) => onChange({ prompt: e.target.value })} />
          </label>
          <div className="form-grid">
            <label>
              Duration (s)
              <input
                type="number"
                step=".1"
                min=".5"
                max="120"
                value={scene.duration}
                onChange={(e) => onChange({ duration: +e.target.value })}
              />
            </label>
            {(image || !scene.asset) && (
              <label>
                Motion
                <select value={scene.motion} onChange={(e) => onChange({ motion: e.target.value as Motion })}>
                  {motions.map(([id, name]) => (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <div className="form-grid">
            <label className="upload-button">
              Upload narration
              <input
                type="file"
                accept="audio/*"
                onChange={(e) => onUpload(e.target.files?.[0], (narration) => onChange({ narration }))}
              />
            </label>
            <button disabled={!scene.text.trim()} onClick={() => onJob('narration')}>
              ♫ {scene.narration ? 'Re-voice' : 'Voice'} this scene
            </button>
          </div>
          {scene.narration && (
            <>
              <audio controls src={assetUrl(scene.narration)} />
              <button onClick={() => onChange({ narration: '' })}>Remove narration</button>
            </>
          )}
        </div>
      </div>
    </article>
  );
}
