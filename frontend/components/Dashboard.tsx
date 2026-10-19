import { assetUrl, isImage, type Project } from '../lib/api';

type Props = {
  projects: Project[];
  busy: boolean;
  onNew: () => void;
  onOpen: (project: Project) => void;
  onDuplicate: (project: Project) => void;
  onDelete: (project: Project) => void;
  onTranslate: (project: Project) => void;
};

export default function Dashboard({ projects, busy, onNew, onOpen, onDuplicate, onDelete, onTranslate }: Props) {
  return (
    <>
      <div className="hero">
        <div>
          <p className="eyebrow">FROM A THOUGHT TO A TIMELINE</p>
          <h1>
            Your words,
            <br />
            <em>in motion.</em>
          </h1>
          <p>
            A little imagination. A whole new frame.
            <br />
            Create films with AI that runs on your machine.
          </p>
          <button className="primary" onClick={onNew}>
            ＋ Create a video
          </button>
        </div>
        <div className="hero-art">
          <div className="orbit one" />
          <div className="orbit two" />
          <div className="film-card">
            <span>FRAME EXPERIMENTS</span>
            <div className="sun" />
            <div className="mountain" />
            <div className="mountain second" />
            <b>A different perspective.</b>
            <small>YOUR NEXT STORY STARTS HERE</small>
          </div>
          <span className="art-label">IMAGINE → CREATE → REFINE</span>
        </div>
      </div>
      <div className="section-title">
        <h2>
          Your projects <small>{projects.length}</small>
        </h2>
        <span>Stored on this device</span>
      </div>
      <div className="project-grid">
        <button className="new-card" onClick={onNew}>
          <span>＋</span>
          <b>Start with an idea</b>
          <small>Build something worth watching</small>
        </button>
        {projects.map((p, i) => {
          const cover = p.scenes.find((s) => isImage(s.asset))?.asset;
          return (
            <div className="project-card" key={p.id}>
              <button className="project-open" onClick={() => onOpen(p)}>
                <div className={'project-art tone' + (i % 3)}>
                  {cover ? <img src={assetUrl(cover)} alt="Project cover" /> : <span>▶</span>}
                  <small>{p.mode === 'video' ? 'AI VIDEO' : 'ANIMATED SLIDESHOW'}</small>
                </div>
                <div className="project-info">
                  <b dir="auto">{p.title}</b>
                  <p>
                    {p.scenes.length} scenes · {p.duration}s · {p.language === 'ur' ? 'اردو' : 'English'}
                    {p.exports.length > 0 && ` · ${p.exports.length} export${p.exports.length > 1 ? 's' : ''}`}
                  </p>
                </div>
              </button>
              <div className="card-actions">
                <button disabled={busy} onClick={() => onDuplicate(p)}>
                  Duplicate
                </button>
                <button disabled={busy || !p.scenes.length} onClick={() => onTranslate(p)}>
                  {p.language === 'ur' ? 'English copy' : 'اردو copy'}
                </button>
                <button disabled={busy} className="danger" onClick={() => onDelete(p)}>
                  Delete
                </button>
              </div>
            </div>
          );
        })}
      </div>
      <div className="workflow-strip">
        <span>
          01 <b>Write your idea</b>
        </span>
        <span>
          02 <b>Shape your story</b>
        </span>
        <span>
          03 <b>Make it move</b>
        </span>
        <span>
          04 <b>Share your film</b>
        </span>
      </div>
    </>
  );
}
