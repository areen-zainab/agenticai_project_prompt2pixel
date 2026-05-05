import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

interface Phase3Manifest {
  exported_at: string;
  final_output_path: string;
  duration_seconds: number;
  scene_count: number;
  transition_style: string;
  subtitles_burned: boolean;
  srt_path?: string;
}

const API = 'http://localhost:8000/api';

const Phase3 = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [phase3Done, setPhase3Done] = useState(false);
  const [manifest, setManifest] = useState<Phase3Manifest | null>(null);
  const [transitionStyle, setTransitionStyle] = useState('fade');
  const [addSubtitles, setAddSubtitles] = useState(true);
  const [videoReady, setVideoReady] = useState(false);

  const loadOutputs = useCallback(async () => {
    try {
      const res = await fetch(`${API}/phase3/outputs`);
      if (res.ok) {
        const d = await res.json();
        if (d.data) {
          setManifest(d.data);
          setPhase3Done(true);
          setVideoReady(true);
        }
      }
    } catch {
      /* Phase 3 not yet run */
    }
  }, []);

  useEffect(() => {
    void loadOutputs();
  }, [loadOutputs]);

  useEffect(() => {
    if (!loading) {
      setLoadingStep(0);
      return;
    }
    const t = setInterval(() => setLoadingStep((p) => (p < 4 ? p + 1 : p)), 8000);
    return () => clearInterval(t);
  }, [loading]);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    setPhase3Done(false);
    setVideoReady(false);
    setManifest(null);
    try {
      const res = await fetch(`${API}/phase3/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transition_style: transitionStyle,
          add_subtitles: addSubtitles,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Phase 3 failed');
      if (data.data) {
        setManifest(data.data.phase3_manifest);
        setPhase3Done(true);
        setVideoReady(true);
      }
    } catch (e: any) {
      setError(e.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const agents = [
    { icon: '🎬', name: 'Scene Collector' },
    { icon: '🔧', name: 'Normalizer' },
    { icon: '✨', name: 'Transitions' },
    { icon: '📝', name: 'Subtitles' },
    { icon: '💾', name: 'Exporter' },
  ];

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400&display=swap');
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        @keyframes pulse { 0%,100%{ opacity:1; } 50%{ opacity:0.5; } }
        @keyframes spin { to { transform: rotate(360deg); } }

        .p3-root { display: flex; min-height: 100vh; background: #0a0a0b; color: #e8e0d0; font-family: 'DM Sans', sans-serif; }

        /* Sidebar */
        .p3-sidebar { width: 240px; min-width: 240px; position: fixed; top: 0; left: 0; bottom: 0; background: #111113; border-right: 1px solid #1e1e22; display: flex; flex-direction: column; padding: 28px 0 24px; z-index: 100; }
        .p3-logo { padding: 0 24px 28px; border-bottom: 1px solid #1e1e22; }
        .p3-logo-eyebrow { font-family: 'DM Mono', monospace; font-size: 9px; letter-spacing: 0.2em; text-transform: uppercase; color: #9e8c6e; margin-bottom: 4px; }
        .p3-logo-title { font-family: 'Playfair Display', serif; font-size: 20px; font-weight: 700; color: #f0e8d8; }
        .p3-nav-sec { padding: 20px 24px 16px; border-bottom: 1px solid #1e1e22; }
        .p3-sec-lbl { font-size: 9px; letter-spacing: 0.15em; text-transform: uppercase; color: #4a4a55; margin-bottom: 12px; }
        .p3-agent-row { display: flex; align-items: center; gap: 10px; padding: 7px 0; }
        .p3-agent-icon { font-size: 13px; width: 20px; text-align: center; }
        .p3-agent-name { flex: 1; font-size: 13px; color: #b0a898; }
        .p3-agent-dot { width: 6px; height: 6px; border-radius: 50%; }
        .p3-agent-dot.idle { background: #4a4a55; }
        .p3-agent-dot.running { background: #9e8c6e; animation: pulse 2s infinite; }
        .p3-agent-dot.done { background: #4a9e6f; }
        .p3-sidebar-footer { margin-top: auto; padding: 16px 24px 0; border-top: 1px solid #1e1e22; font-size: 10px; color: #3a3a44; font-family: 'DM Mono', monospace; }

        /* Main */
        .p3-main { margin-left: 240px; flex: 1; display: flex; flex-direction: column; }
        .p3-topbar { position: sticky; top: 0; z-index: 50; background: rgba(10,10,11,0.92); backdrop-filter: blur(8px); border-bottom: 1px solid #1e1e22; padding: 0 40px; height: 52px; display: flex; align-items: center; justify-content: space-between; }
        .p3-breadcrumb { font-family: 'DM Mono', monospace; font-size: 11px; color: #4a4a55; display: flex; align-items: center; gap: 8px; }
        .p3-breadcrumb span { color: #9e8c6e; }
        .p3-phase-badge { font-family: 'DM Mono', monospace; font-size: 10px; letter-spacing: 0.12em; background: rgba(158,140,110,0.12); color: #9e8c6e; border: 1px solid rgba(158,140,110,0.25); border-radius: 4px; padding: 4px 10px; text-transform: uppercase; }
        .p3-content { padding: 48px 40px 80px; max-width: 880px; }

        /* Hero */
        .p3-hero { margin-bottom: 44px; }
        .p3-hero-eyebrow { font-family: 'DM Mono', monospace; font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase; color: #9e8c6e; margin-bottom: 12px; }
        .p3-hero-title { font-family: 'Playfair Display', serif; font-size: 48px; font-weight: 700; color: #f0e8d8; letter-spacing: -0.03em; line-height: 1.1; margin-bottom: 12px; }
        .p3-hero-sub { font-size: 15px; color: #6a6268; font-weight: 300; max-width: 480px; line-height: 1.6; }

        /* Error */
        .p3-error-banner { background: rgba(208,128,128,0.1); border-left: 4px solid #D08080; padding: 16px 20px; border-radius: 4px; margin-bottom: 24px; display: flex; gap: 12px; }

        /* Run box */
        .p3-run-box { background: #111113; border: 1px solid #1e1e22; border-radius: 12px; padding: 32px; margin-bottom: 32px; }
        .p3-run-lede { color: #6a6268; font-size: 14px; line-height: 1.6; margin-bottom: 24px; }
        .p3-run-controls { display: flex; flex-direction: column; gap: 16px; margin-bottom: 24px; }
        .p3-control-group { display: flex; flex-direction: column; gap: 8px; }
        .p3-control-label { font-size: 13px; font-weight: 500; color: #b0a898; }
        .p3-select { background: #0d0d0f; border: 1px solid #1e1e22; border-radius: 6px; padding: 10px 12px; color: #d8d0c0; font-family: 'DM Sans', sans-serif; font-size: 13px; cursor: pointer; }
        .p3-checkbox-wrap { display: flex; align-items: center; gap: 8px; }
        .p3-checkbox { width: 16px; height: 16px; cursor: pointer; accent-color: #9e8c6e; }
        .p3-run-btn { background: linear-gradient(135deg, #9e8c6e 0%, #8a7a60 100%); color: #fff; border: none; border-radius: 8px; padding: 16px 32px; font-family: 'DM Sans', sans-serif; font-size: 15px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 12px; transition: all 0.3s; box-shadow: 0 4px 12px rgba(158,140,110,0.25); width: 100%; justify-content: center; }
        .p3-run-btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(158,140,110,0.35); }
        .p3-run-btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .p3-spinner { width: 18px; height: 18px; border: 2px solid rgba(255,255,255,0.25); border-radius: 50%; border-top-color: #fff; animation: spin 0.8s linear infinite; }

        /* Processing view */
        .p3-gen-box { background: #111113; border: 1px solid #1e1e22; border-radius: 12px; padding: 28px 32px; margin-bottom: 32px; }
        .p3-gen-title { font-family: 'Playfair Display', serif; font-size: 18px; color: #f0e8d8; margin-bottom: 6px; display: flex; align-items: center; gap: 10px; }
        .p3-gen-sub { font-size: 13px; color: #6a6268; margin-bottom: 20px; }
        .p3-gen-strip { display: flex; background: #0e0e10; border: 1px solid #1e1e22; border-radius: 8px; overflow: hidden; flex-wrap: wrap; }
        .p3-gen-step { flex: 1; min-width: 140px; padding: 14px 8px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 6px; color: #4a4a55; border-right: 1px solid #1e1e22; border-bottom: 1px solid #1e1e22; transition: all 0.4s; }
        .p3-gen-step:nth-child(5n) { border-right: none; }
        .p3-gen-step.gs-done { color: #4a9e6f; background: rgba(74,158,111,0.07); }
        .p3-gen-step.gs-active { color: #9e8c6e; background: rgba(158,140,110,0.08); font-weight: 600; }
        .p3-gen-step-icon { font-size: 18px; }
        .p3-gen-step-label { font-size: 11px; }
        .p3-gen-step-status { font-family: 'DM Mono', monospace; font-size: 9px; letter-spacing: 0.1em; margin-top: 2px; }
        .gs-done .p3-gen-step-status { color: #4a9e6f; }
        .gs-active .p3-gen-step-status { color: #9e8c6e; animation: pulse 2s infinite; }

        /* Video display */
        .p3-video-section { margin-bottom: 32px; }
        .p3-section-hd { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #1a1a20; }
        .p3-section-num { font-family: 'DM Mono', monospace; font-size: 10px; color: #9e8c6e; opacity: 0.6; }
        .p3-section-title { font-family: 'Playfair Display', serif; font-size: 20px; font-weight: 600; color: #d8d0c0; flex: 1; }
        
        .p3-video-wrap { background: #000; border-radius: 8px; overflow: hidden; border: 1px solid #1e1e22; margin-bottom: 20px; }
        .p3-video { width: 100%; max-height: 600px; display: block; }

        .p3-metadata { background: #111113; border: 1px solid #1e1e22; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
        .p3-metadata-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
        .p3-metadata-item { }
        .p3-metadata-label { font-family: 'DM Mono', monospace; font-size: 9px; letter-spacing: 0.15em; text-transform: uppercase; color: #4a4a55; margin-bottom: 4px; }
        .p3-metadata-value { font-size: 14px; color: #d8d0c0; }

        .p3-download-btn { background: linear-gradient(135deg, #9e8c6e 0%, #8a7a60 100%); color: #fff; border: none; border-radius: 8px; padding: 12px 24px; font-family: 'DM Sans', sans-serif; font-size: 14px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; transition: all 0.2s; }
        .p3-download-btn:hover { transform: translateY(-1px); }

        /* CTA bar */
        .p3-cta-bar { padding-top: 32px; border-top: 1px solid #1a1a20; display: flex; align-items: center; justify-content: space-between; }
        .p3-cta-hint { font-size: 12px; color: #3a3a44; font-family: 'DM Mono', monospace; }
        .p3-btn-back { background: transparent; color: #9a9288; border: 1px solid #2a2a30; border-radius: 7px; padding: 11px 24px; font-family: 'DM Sans', sans-serif; font-size: 13px; font-weight: 500; cursor: pointer; transition: all 0.15s; }
        .p3-btn-back:hover { border-color: #3a3a40; color: #c8c0b0; }
        .p3-btn-next { background: linear-gradient(135deg, #9e8c6e 0%, #8a7a60 100%); color: #fff; border: none; border-radius: 7px; padding: 11px 24px; font-family: 'DM Sans', sans-serif; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s; display: flex; align-items: center; gap: 8px; }
        .p3-btn-next:hover:not(:disabled) { transform: translateY(-1px); }
        .p3-btn-next:disabled { opacity: 0.6; cursor: not-allowed; }
      `}</style>

      <div className="p3-root">
        {/* Sidebar */}
        <aside className="p3-sidebar">
          <div className="p3-logo">
            <div className="p3-logo-eyebrow">Cutting Room</div>
            <div className="p3-logo-title">Montage</div>
          </div>
          <div className="p3-nav-sec">
            <div className="p3-sec-lbl">Composition Agents</div>
            {agents.map((a) => (
              <div key={a.name} className="p3-agent-row">
                <span className="p3-agent-icon">{a.icon}</span>
                <span className="p3-agent-name">{a.name}</span>
                <span
                  className={`p3-agent-dot ${
                    loading ? 'running' : phase3Done ? 'done' : 'idle'
                  }`}
                />
              </div>
            ))}
          </div>
          <div className="p3-sidebar-footer">CS-4015 Agentic AI · FAST NUCES</div>
        </aside>

        {/* Main */}
        <main className="p3-main">
          <div className="p3-topbar">
            <div className="p3-breadcrumb">
              Montage <span>/</span> Phase 3 — Cutting Room
            </div>
            <div className="p3-phase-badge">Phase 3 of 3</div>
          </div>

          <div className="p3-content">
            <div className="p3-hero">
              <div className="p3-hero-eyebrow">Phase 3 · Cutting Room</div>
              <h1 className="p3-hero-title">
                Final Video Composition &amp;<br />Assembly
              </h1>
              <p className="p3-hero-sub">
                Stitch all scenes together with transitions and optional subtitles
                to create the final output video.
              </p>
            </div>

            {error && (
              <div className="p3-error-banner">
                <span>⚠️</span>
                <div>
                  <strong>Error</strong>
                  <br />
                  {error}
                </div>
              </div>
            )}

            {/* ── Run button (idle, not yet done) ── */}
            {!phase3Done && !loading && (
              <div className="p3-run-box">
                <div className="p3-run-lede">
                  Click below to stitch all Phase 2 scene videos into a single
                  final output with transitions and optional subtitles.
                </div>
                <div className="p3-run-controls">
                  <div className="p3-control-group">
                    <label className="p3-control-label">Transition Style</label>
                    <select
                      className="p3-select"
                      value={transitionStyle}
                      onChange={(e) => setTransitionStyle(e.target.value)}
                    >
                      <option value="fade">Fade</option>
                      <option value="cut">Hard Cut</option>
                      <option value="wipe_left">Wipe Left</option>
                      <option value="wipe_right">Wipe Right</option>
                      <option value="dissolve">Dissolve</option>
                      <option value="fade_black">Fade to Black</option>
                    </select>
                  </div>
                  <div className="p3-control-group">
                    <label className="p3-checkbox-wrap">
                      <input
                        type="checkbox"
                        className="p3-checkbox"
                        checked={addSubtitles}
                        onChange={(e) => setAddSubtitles(e.target.checked)}
                      />
                      <span>Add subtitles to final video</span>
                    </label>
                  </div>
                </div>
                <button className="p3-run-btn" onClick={handleRun}>
                  ▶ Run Phase 3
                </button>
              </div>
            )}

            {/* ── Processing view ── */}
            {loading && (
              <div className="p3-gen-box">
                <div className="p3-gen-title">
                  <div className="p3-spinner" />
                  Composing Final Video…
                </div>
                <div className="p3-gen-sub">
                  Stitching scenes with transitions. This may take a few minutes.
                </div>
                <div className="p3-gen-strip">
                  {agents.map((a, i) => {
                    const cls =
                      i < loadingStep
                        ? 'gs-done'
                        : i === loadingStep
                        ? 'gs-active'
                        : '';
                    return (
                      <div key={a.name} className={`p3-gen-step ${cls}`}>
                        <span className="p3-gen-step-icon">{a.icon}</span>
                        <span className="p3-gen-step-label">{a.name}</span>
                        <span className="p3-gen-step-status">
                          {i < loadingStep
                            ? '✓ DONE'
                            : i === loadingStep
                            ? 'RUNNING…'
                            : 'PENDING'}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Final video display ── */}
            {phase3Done && !loading && videoReady && manifest && (
              <div className="p3-video-section">
                <div className="p3-section-hd">
                  <span className="p3-section-num">01</span>
                  <span className="p3-section-title">Final Output</span>
                </div>

                <div className="p3-video-wrap">
                  <video
                    className="p3-video"
                    src={`${API}/phase3/video`}
                    controls
                    preload="metadata"
                  />
                </div>

                <div className="p3-metadata">
                  <div className="p3-metadata-grid">
                    <div className="p3-metadata-item">
                      <div className="p3-metadata-label">Duration</div>
                      <div className="p3-metadata-value">
                        {manifest.duration_seconds.toFixed(1)}s
                      </div>
                    </div>
                    <div className="p3-metadata-item">
                      <div className="p3-metadata-label">Scenes</div>
                      <div className="p3-metadata-value">{manifest.scene_count}</div>
                    </div>
                    <div className="p3-metadata-item">
                      <div className="p3-metadata-label">Transition</div>
                      <div className="p3-metadata-value">
                        {manifest.transition_style}
                      </div>
                    </div>
                    <div className="p3-metadata-item">
                      <div className="p3-metadata-label">Subtitles</div>
                      <div className="p3-metadata-value">
                        {manifest.subtitles_burned ? 'Yes' : 'No'}
                      </div>
                    </div>
                  </div>
                </div>

                <a
                  className="p3-download-btn"
                  href={`${API}/phase3/video`}
                  download="final_output.mp4"
                >
                  ⬇️ Download Video
                </a>
              </div>
            )}

            <div className="p3-cta-bar">
              <div className="p3-cta-hint">← Studio Floor</div>
              <div style={{ display: 'flex', gap: '12px' }}>
                <button className="p3-btn-back" onClick={() => navigate('/phase2')}>
                  ← Back to Phase 2
                </button>
                {phase3Done && (
                  <button
                    className="p3-btn-next"
                    onClick={() => navigate('/edit')}
                  >
                    Edit Video → 
                  </button>
                )}
              </div>
            </div>
          </div>
        </main>
      </div>
    </>
  );
};

export default Phase3;
