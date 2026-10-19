import type { Status } from '../lib/api';

type Props = {
  tab: string;
  locked: boolean;
  status: Status | null;
  onTab: (tab: string) => void;
  onNew: () => void;
};

export default function Sidebar({ tab, locked, status, onTab, onNew }: Props) {
  return (
    <aside>
      <a className="brand" onClick={() => onTab('dashboard')}>
        <span className="mark">F</span>frame<span className="brand-dot">●</span>
      </a>
      <p className="eyebrow">LOCAL VIDEO STUDIO</p>
      <nav>
        <button className={tab === 'dashboard' ? 'selected' : ''} onClick={() => onTab('dashboard')}>
          ▦ <span>My projects</span>
        </button>
        <button className={tab === 'wizard' ? 'selected' : ''} disabled={locked} onClick={onNew}>
          ＋ <span>Create a video</span>
        </button>
        <button className={tab === 'settings' ? 'selected' : ''} onClick={() => onTab('settings')}>
          ⚙ <span>Models & settings</span>
        </button>
      </nav>
      <div className="local-card">
        <span className="led" /> Your studio. Your machine.
        <p>Scripts, media, and renders stay local.</p>
        <small>
          Ollama {status?.ollama?.online ? 'connected' : 'offline'}
          <br />
          ComfyUI {status?.comfy?.online ? 'connected' : 'offline'}
        </small>
      </div>
      <div className="sidebar-foot">
        Made for your next idea.
        <br />
        <b>FRAME / 01</b>
      </div>
    </aside>
  );
}
