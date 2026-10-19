import type { Job } from '../lib/api';

const labels: Record<string, string> = {
  storyboard: 'Storyboard',
  describe: 'Photo descriptions',
  visuals: 'Visuals',
  narration: 'Narration',
  render: 'Render',
};

type Props = {
  jobs: Job[];
  locked: boolean;
  onCancel: (job: Job) => void;
  onRetry: (job: Job) => void;
};

export default function JobsPanel({ jobs, locked, onCancel, onRetry }: Props) {
  if (!jobs.length) return null;
  return (
    <div className="jobs">
      <h3>Processing activity</h3>
      {jobs.map((j) => (
        <div key={j.id} className="job">
          <div>
            <b className={j.status === 'refused' ? 'refused' : ''}>
              {labels[j.kind] || j.kind} · {j.status}
            </b>
            <p>{j.stage}</p>
            <progress max="100" value={j.progress} />
          </div>
          {['queued', 'running'].includes(j.status) ? (
            <button onClick={() => onCancel(j)}>Cancel</button>
          ) : ['failed', 'interrupted', 'cancelled'].includes(j.status) ? (
            <button disabled={locked} onClick={() => onRetry(j)}>
              Retry
            </button>
          ) : null}
        </div>
      ))}
    </div>
  );
}
