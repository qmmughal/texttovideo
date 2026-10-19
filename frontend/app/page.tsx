'use client';
import { useEffect, useState } from 'react';
import Dashboard from '../components/Dashboard';
import Editor from '../components/Editor';
import JobsPanel from '../components/JobsPanel';
import SettingsView, { type WorkflowText } from '../components/SettingsView';
import SetupView from '../components/SetupView';
import Sidebar from '../components/Sidebar';
import Wizard from '../components/Wizard';
import {
  call,
  defaultExport,
  freshProject,
  newScene,
  uploadFile,
  SYSTEM,
  type Preset,
  type Setup,
  type Job,
  type Project,
  type Settings,
  type Status,
} from '../lib/api';

const ACTIVE = ['running', 'queued'];
const TAB_NAMES: Record<string, string> = {
  settings: 'SETTINGS',
  setup: 'SETUP CHECK',
  editor: 'STORYBOARD',
  wizard: 'NEW VIDEO',
  dashboard: 'PROJECTS',
};

export default function Studio() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [tab, setTab] = useState('dashboard');
  const [settings, setSettings] = useState<Settings | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [workflow, setWorkflow] = useState<WorkflowText>({ image_workflow: '{}', video_workflow: '{}' });
  const [options, setOptions] = useState(defaultExport);
  const [preview, setPreview] = useState('');
  const [setup, setSetup] = useState<Setup | null>(null);
  const [presets, setPresets] = useState<Preset[]>([]);

  const active = jobs.find((j) => j.project === project?.id && ACTIVE.includes(j.status));
  const locked = busy || !!active;
  const setupDone =
    !setup ||
    (setup.ollama.state === 'running' &&
      !!setup.settings.model &&
      setup.ollama.models.includes(setup.settings.model) &&
      setup.voice.available);

  async function guard(action: () => Promise<void>) {
    setError('');
    setBusy(true);
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function refresh() {
    const [p, j] = await Promise.all([call<Project[]>('/projects'), call<Job[]>('/jobs')]);
    setProjects(p);
    setJobs(j);
  }

  useEffect(() => {
    guard(async () => {
      await refresh();
      const s = await call<Settings>('/settings');
      setSettings(s);
      setWorkflow({
        image_workflow: JSON.stringify(s.image_workflow, null, 2),
        video_workflow: JSON.stringify(s.video_workflow, null, 2),
      });
      setStatus(await call('/status'));
      setSetup(await call('/setup'));
      setPresets(await call('/presets'));
    });
  }, []);

  async function reloadSettings() {
    const [s, st, su] = await Promise.all([call<Settings>('/settings'), call<Status>('/status'), call<Setup>('/setup')]);
    setSettings(s);
    setStatus(st);
    setSetup(su);
  }

  // Poll jobs; when one finishes, reload the open project so generated assets appear.
  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const latest = await call<Job[]>('/jobs');
        setJobs((old) => {
          const finished = old.some(
            (v) => ACTIVE.includes(v.status) && latest.some((n) => n.id === v.id && !ACTIVE.includes(n.status)),
          );
          const setupFinished = old.some(
            (v) => v.project === SYSTEM && ACTIVE.includes(v.status) && latest.some((n) => n.id === v.id && !ACTIVE.includes(n.status)),
          );
          if (setupFinished) reloadSettings().catch(() => {});
          if (finished) {
            call<Project[]>('/projects').then(setProjects);
            if (project?.id) {
              call<Project>('/projects/' + project.id).then((p) => {
                setProject(p);
                setDirty(false);
                if (p.exports.length) setPreview(p.exports[p.exports.length - 1].asset);
              });
            }
          }
          return latest;
        });
      } catch {}
    }, 1500);
    return () => clearInterval(timer);
  }, [project?.id]);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);

  function update(value: Partial<Project>) {
    if (project) {
      setProject({ ...project, ...value });
      setDirty(true);
    }
  }

  async function save(value: Project | null = project) {
    if (!value) return;
    const saved = await call<Project>('/projects' + (value.id ? '/' + value.id : ''), value.id ? 'PUT' : 'POST', value);
    setProject(saved);
    setDirty(false);
    await refresh();
    return saved;
  }

  async function job(kind: string, extra: object = {}, value: Project | null = project) {
    await guard(async () => {
      const saved = await save(value);
      if (saved) {
        const body = kind === 'render' ? options : kind === 'visuals' ? { ...extra, aspect: options.width / options.height } : extra;
        await call(`/projects/${saved.id}/jobs/${kind}`, 'POST', body);
        await refresh();
        setTab('editor');
      }
    });
  }

  async function upload(file: File | undefined, apply: (name: string) => void) {
    if (!file) return;
    await guard(async () => {
      apply(await uploadFile(file));
      setNotice('Uploaded locally. Save the project to keep this edit.');
    });
  }

  async function begin() {
    await guard(async () => {
      if (dirty) await save();
      setProject(freshProject());
      setTab('wizard');
      setDirty(false);
    });
  }

  async function open(p: Project) {
    await guard(async () => {
      if (dirty && project) await save();
      setProject(p);
      setDirty(false);
      setPreview(p.exports.at(-1)?.asset || '');
      setTab('editor');
    });
  }

  async function fromPhotos(files: File[]) {
    if (!project) return;
    let created: Project | undefined;
    await guard(async () => {
      const duration = Math.max(1.5, Math.round((project.duration / files.length) * 10) / 10);
      const scenes = [];
      for (const [i, file] of files.entries()) {
        setNotice(`Uploading photo ${i + 1} of ${files.length}…`);
        scenes.push(newScene({ asset: await uploadFile(file), duration }));
      }
      setNotice('');
      created = await save({ ...project, mode: 'slideshow', scenes });
      setTab('editor');
    });
    if (created && settings?.vision_model) await job('describe', {}, created);
    else if (created) setNotice('Photos added. Write a caption for each scene, or choose a vision model in settings.');
  }

  async function duplicate(p: Project) {
    await guard(async () => {
      await call(`/projects/${p.id}/duplicate`, 'POST');
      await refresh();
      setNotice(`Duplicated “${p.title}”.`);
    });
  }

  async function remove(p: Project) {
    if (!window.confirm(`Delete “${p.title}” and its exports? Media used by other projects is kept.`)) return;
    await guard(async () => {
      await call(`/projects/${p.id}`, 'DELETE');
      if (project?.id === p.id) {
        setProject(null);
        setDirty(false);
      }
      await refresh();
      setNotice(`Deleted “${p.title}”.`);
    });
  }

  async function saveSettings() {
    if (!settings) return;
    await guard(async () => {
      const value = {
        ...settings,
        image_workflow: JSON.parse(workflow.image_workflow),
        video_workflow: JSON.parse(workflow.video_workflow),
      };
      setSettings(await call('/settings', 'PUT', value));
      setStatus(await call('/status'));
      setSetup(await call('/setup'));
      setNotice('Settings saved and connections refreshed.');
    });
  }

  async function install(kind: string, extra: object) {
    await guard(async () => {
      await call(`/setup/jobs/${kind}`, 'POST', extra);
      await refresh();
    });
  }

  async function useSettings(value: Partial<Settings>) {
    if (!settings) return;
    await guard(async () => {
      await call('/settings', 'PUT', { ...settings, ...value });
      await reloadSettings();
      setNotice('Setting updated.');
    });
  }

  async function translate(p: Project) {
    const language = p.language === 'ur' ? 'en' : 'ur';
    await guard(async () => {
      const result = await call<{ project: Project }>(`/projects/${p.id}/translate`, 'POST', { language });
      await refresh();
      setProject(result.project);
      setPreview('');
      setDirty(false);
      setTab('editor');
      setNotice(`Translating into ${language === 'ur' ? 'Urdu' : 'English'}. Voice and render the copy when it finishes.`);
    });
  }

  async function savePreset(name: string) {
    if (!project) return;
    await guard(async () => {
      await call('/presets', 'POST', { name, options, logo: project.logo, music: project.music });
      setPresets(await call('/presets'));
      setNotice(`Saved the look “${name}”.`);
    });
  }

  async function deletePreset(preset: Preset) {
    await guard(async () => {
      await call(`/presets/${preset.id}`, 'DELETE');
      setPresets(await call('/presets'));
    });
  }

  const projectJobs = jobs.filter((j) => j.project === project?.id).slice(0, 3);

  return (
    <div className="app">
      <Sidebar tab={tab} locked={locked} status={status} setupDone={setupDone} onTab={setTab} onNew={begin} />
      <main>
        <header>
          <span>
            WORKSPACE <span className="muted">/ {TAB_NAMES[tab]}</span>
          </span>
          <span className="private">◉ LOCAL & PRIVATE</span>
        </header>
        {error && (
          <div className="alert" role="alert">
            {error}
            <button onClick={() => setError('')}>×</button>
          </div>
        )}
        {notice && (
          <div className="notice" onClick={() => setNotice('')}>
            {notice} ×
          </div>
        )}
        {tab === 'dashboard' && !setupDone && (
          <div className="setup-banner">
            <div>
              <b>Finish setting up AI on this computer</b>
              <p className="small">A quick check recommends models that fit your memory and graphics, and installs them for you.</p>
            </div>
            <button className="primary" onClick={() => setTab('setup')}>
              Open setup check →
            </button>
          </div>
        )}
        {tab === 'setup' && (
          <SetupView
            setup={setup}
            jobs={jobs.filter((j) => j.project === SYSTEM)}
            busy={busy}
            onInstall={install}
            onUse={useSettings}
            onCancel={(j) => guard(async () => void (await call(`/jobs/${j.id}/cancel`, 'POST')))}
            onRefresh={() => guard(reloadSettings)}
          />
        )}
        {tab === 'dashboard' && (
          <Dashboard
            projects={projects}
            busy={busy}
            onNew={begin}
            onOpen={open}
            onDuplicate={duplicate}
            onDelete={remove}
            onTranslate={translate}
          />
        )}
        {tab === 'wizard' && project && (
          <Wizard
            project={project}
            options={options}
            busy={busy}
            visionModel={settings?.vision_model || ''}
            update={update}
            setOptions={setOptions}
            onStoryboard={() => job('storyboard')}
            onBlank={() =>
              guard(async () => {
                await save();
                setTab('editor');
              })
            }
            onPhotos={fromPhotos}
          />
        )}
        {tab === 'editor' && project && (
          <Editor
            project={project}
            options={options}
            preview={preview}
            locked={locked}
            dirty={dirty}
            canDescribe={!!settings?.vision_model}
            canAlign={!!setup?.words.whisper && !!setup?.words.downloaded}
            update={update}
            setOptions={setOptions}
            setPreview={setPreview}
            onSave={() =>
              guard(async () => {
                await save();
                setNotice('Project saved.');
              })
            }
            onJob={job}
            onUpload={upload}
            presets={presets}
            onSavePreset={savePreset}
            onDeletePreset={deletePreset}
          />
        )}
        {tab === 'settings' && settings && (
          <SettingsView
            settings={settings}
            status={status}
            workflow={workflow}
            busy={busy}
            setSettings={setSettings}
            setWorkflow={setWorkflow}
            onSave={saveSettings}
            onRefresh={() => guard(async () => setStatus(await call('/status')))}
          />
        )}
        {tab === 'editor' && (
          <JobsPanel
            jobs={projectJobs}
            locked={locked}
            onCancel={(j) => guard(async () => void (await call(`/jobs/${j.id}/cancel`, 'POST')))}
            onRetry={(j) =>
              guard(async () => {
                if (dirty) await save();
                await call(`/jobs/${j.id}/retry`, 'POST');
                await refresh();
              })
            }
          />
        )}
        <footer>
          FRAME STUDIO <span>Local by design. Creative by nature.</span>
        </footer>
      </main>
    </div>
  );
}
