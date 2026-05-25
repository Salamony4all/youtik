import React, { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Play, Terminal, Download, Settings, Layers, Scissors, Cpu, CheckCircle2, AlertCircle, Link as LinkIcon, Sparkles, ChevronRight, ChevronDown, Monitor, Layout, Sun, Moon, Check, Edit3, Save, Plus, Trash2, Pause, Mic, PenTool, Music, Share2, ExternalLink, Loader, RotateCcw } from 'lucide-react';
import axios from 'axios';
import RFB from '@novnc/novnc';

const getApiBase = () => {
  if (import.meta.env.VITE_API_BASE) {
    return import.meta.env.VITE_API_BASE;
  }
  // Robust dynamic fallback for Render and Railway hosting environments
  const host = window.location.hostname;
  if (host.includes("onrender.com") || host.includes(".up.railway.app")) {
    if (host.includes("-frontend")) {
      return `https://${host.replace("-frontend", "-backend")}`;
    }
    if (host.includes("frontend")) {
      return `https://${host.replace("frontend", "backend")}`;
    }
  }
  return "http://localhost:8000";
};
const API_BASE = getApiBase();


const clipSteps = [
  { id: 'INGESTION', title: 'Smart Ingest', icon: LinkIcon, color: 'text-blue-400' },
  { id: 'VOCAL_ANALYSIS', title: 'Vocal Analysis', icon: Cpu, color: 'text-purple-400' },
  { id: 'SEMANTICS', title: 'Semantic Mapping', icon: Sparkles, color: 'text-yellow-400' },
  { id: 'WAITING_FOR_REVIEW', title: 'Human Review', icon: Edit3, color: 'text-orange-400' },
  { id: 'SLICING', title: 'Precision Slicing', icon: Scissors, color: 'text-pink-400' },
  { id: 'COMPOSITING', title: 'Studio Composite', icon: Layers, color: 'text-red-500' },
];

const createSteps = [
  { id: 'SCRIPT_GENERATION', title: 'AI Scriptwriting', icon: PenTool, color: 'text-yellow-400' },
  { id: 'TTS_SYNTHESIS', title: 'Vocal Synthesis', icon: Mic, color: 'text-emerald-400' },
  { id: 'MUSIC_GENERATION', title: 'Music Engine', icon: Music, color: 'text-blue-500' },
  { id: 'COMPOSITING', title: 'Studio Composite', icon: Layers, color: 'text-red-500' },
];

const statusProgressMap = {
  IDLE: 0,
  STARTING: 3,
  INGESTION: 15,
  VOCAL_ANALYSIS: 30,
  CORRECTING_LYRICS: 43,
  SEMANTICS: 55,
  WAITING_FOR_REVIEW: 60,
  RESUMING: 70,
  SLICING: 82,
  SCRIPT_GENERATION: 20,
  TTS_SYNTHESIS: 45,
  MUSIC_GENERATION: 70,
  COMPOSITING: 90,
  COMPLETED: 100,
  ERROR: 100,
};

const MUSIC_GENRES = ["Pop", "Hip-Hop", "Cinematic", "Egyptian Folk", "Electronic", "Lo-Fi", "Rock", "Jazz", "Synthwave", "Trap", "Classical", "Ambient", "Orchestral", "EDM", "Acoustic", "Metal", "R&B", "Reggae", "Country", "Techno", "House", "Phonk"];

const PUBLISH_PLATFORMS = [
  { id: 'tiktok',    icon: '🎵', name: 'TikTok',          color: '#FE2C55' },
  { id: 'youtube',   icon: '▶️',  name: 'YouTube Shorts',  color: '#FF0000' },
  { id: 'instagram', icon: '📸', name: 'Instagram Reels', color: '#E1306C' },
  { id: 'twitter',   icon: '🐦', name: 'X / Twitter',     color: '#1DA1F2' },
];

const LiveViewer = ({ jobId, onClose }) => {
  const containerRef = useRef(null);
  const rfbRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;
    
    // Construct WebSocket URL matching the FastAPI VNC proxy endpoint
    const wsUrl = API_BASE.replace('http', 'ws') + `/api/vnc/${jobId}`;
    
    try {
      rfbRef.current = new RFB(containerRef.current, wsUrl, {
        credentials: { password: '' },
        shared: true,
        wsProtocols: []
      });
      rfbRef.current.scaleViewport = true;
      rfbRef.current.resizeSession = true;
    } catch (e) {
      console.error("noVNC init error:", e);
    }

    return () => {
      if (rfbRef.current) {
        rfbRef.current.disconnect();
      }
    };
  }, [jobId]);

  return (
    <div className="fixed inset-0 z-[100] bg-black/90 flex flex-col items-center justify-center">
      <div className="w-full h-16 bg-gray-900 border-b border-gray-800 flex items-center justify-between px-6">
        <div className="flex items-center space-x-3">
          <Monitor className="text-blue-500 w-5 h-5" />
          <h2 className="text-lg font-medium text-white">Live Browser Viewer</h2>
          <span className="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full animate-pulse flex items-center">
             <div className="w-1.5 h-1.5 bg-white rounded-full mr-1.5" />
             LIVE
          </span>
        </div>
        <button 
          onClick={onClose}
          className="text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg transition-colors text-sm font-medium"
        >
          Close Viewer
        </button>
      </div>
      <div 
        ref={containerRef} 
        className="flex-1 w-full flex items-center justify-center overflow-hidden relative"
      />
    </div>
  );
};


const PublishDropdown = ({ clip, publishStatus, setPublishStatus, googleUser, setGoogleUser, handleGoogleSignIn, handleGoogleSignOut, isGoogleSigningIn, googleLoginDetail, triggerExtensionSync, setActiveVncJobId }) => {
  const [isOpen, setIsOpen] = useState(false);
  const buttonRef = useRef(null);
  const dropdownRef = useRef(null);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });
  const [saveAsDraft, setSaveAsDraft] = useState(true);
  const [showBrowser, setShowBrowser] = useState(true);

  // Calculate position from the button's bounding rect
  const updatePosition = () => {
    if (!buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();
    const dropdownWidth = 300;
    // Position above the button, aligned to the right edge
    let left = rect.right - dropdownWidth;
    // Prevent going off-screen left
    if (left < 8) left = 8;
    // Prevent going off-screen right
    if (left + dropdownWidth > window.innerWidth - 8) left = window.innerWidth - dropdownWidth - 8;
    setDropdownPos({
      top: rect.top - 12, // 12px gap above button
      left,
    });
  };

  useEffect(() => {
    if (!isOpen) return;
    updatePosition();
    window.addEventListener('scroll', updatePosition, true);
    window.addEventListener('resize', updatePosition);
    return () => {
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
    };
  }, [isOpen]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target) &&
        buttonRef.current && !buttonRef.current.contains(e.target)
      ) {
        setIsOpen(false);
      }
    };
    if (isOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const handlePublish = async (platform) => {
    const key = `${clip.filename}_${platform.id}`;
    setPublishStatus(prev => ({ ...prev, [key]: { status: 'LAUNCHING', detail: 'Starting…' } }));

    try {
      const res = await axios.post(`${API_BASE}/publish`, {
        video_path: clip.url,
        platform: platform.id,
        caption: clip.filename.replace('.mp4', '').replace(/_/g, ' '),
        save_as_draft: saveAsDraft,
        headless: !showBrowser,
      });

      const jobId = res.data.job_id;
      setPublishStatus(prev => ({ ...prev, [key]: { status: 'LAUNCHING', detail: 'Browser launching…', jobId } }));

      const poll = setInterval(async () => {
        try {
          const statusRes = await axios.get(`${API_BASE}/publish/status/${jobId}`);
          const { status: st, detail, vnc_active } = statusRes.data;
          setPublishStatus(prev => ({ ...prev, [key]: { status: st, detail, jobId } }));
          
          if (vnc_active && showBrowser) {
            setActiveVncJobId(jobId);
          }

          if (st === 'PUBLISHED' || st === 'ERROR') clearInterval(poll);
        } catch { clearInterval(poll); }
      }, 2000);
    } catch (err) {
      setPublishStatus(prev => ({ ...prev, [key]: { status: 'ERROR', detail: err.message } }));
    }
  };

  const getStatusForPlatform = (platformId) => {
    return publishStatus[`${clip.filename}_${platformId}`];
  };

  return (
    <>
      <button
        ref={buttonRef}
        onClick={(e) => { e.stopPropagation(); setIsOpen(!isOpen); }}
        className="w-10 h-10 sm:w-12 sm:h-12 bg-gradient-to-br from-purple-500 to-pink-500 text-white rounded-xl sm:rounded-2xl flex items-center justify-center shadow-xl hover:scale-110 transition-all duration-300 active:scale-95"
        title="Publish to social media"
      >
        <Share2 className="w-4 h-4 sm:w-5 sm:h-5" />
      </button>

      {ReactDOM.createPortal(
        <>
          <AnimatePresence>
            {isOpen && (
            <motion.div
              ref={dropdownRef}
              initial={{ opacity: 0, y: 10, scale: 0.92 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.92 }}
              transition={{ type: 'spring', stiffness: 400, damping: 25 }}
              style={{
                position: 'fixed',
                top: dropdownPos.top,
                left: dropdownPos.left,
                width: 300,
                transform: 'translateY(-100%)',
              }}
              className="bg-white dark:bg-[#1c1c1e] border border-slate-200 dark:border-white/15 rounded-2xl shadow-[0_25px_80px_rgba(0,0,0,0.35)] z-[9999] overflow-hidden"
            >
              {/* Header */}
              <div className="px-5 py-3.5 border-b border-slate-100 dark:border-white/10 bg-gradient-to-r from-purple-500/5 to-pink-500/5 dark:from-purple-500/10 dark:to-pink-500/10">
                <div className="flex items-center gap-2.5">
                  <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                    <Share2 size={12} className="text-white" />
                  </div>
                  <span className="text-[11px] font-black uppercase tracking-[0.15em] text-slate-700 dark:text-slate-200">Publish & Share</span>
                </div>
              </div>

              {/* Google Master Auth Card */}
              <div className="p-3 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.01]">
                {googleUser ? (
                  <div className="flex items-center gap-3 p-3 bg-white dark:bg-[#252528] rounded-xl border border-slate-100 dark:border-white/5 shadow-sm">
                    <img 
                      src={googleUser.picture} 
                      alt={googleUser.name} 
                      className="w-9 h-9 rounded-full border border-purple-500/20"
                      onError={(e) => { e.target.src = "https://lh3.googleusercontent.com/a/default-user=s96-c"; }}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-black text-slate-800 dark:text-white flex items-center gap-1.5">
                        {googleUser.name}
                        <span className="text-[9px] bg-green-500/10 dark:bg-green-500/20 text-green-600 dark:text-green-400 font-extrabold px-1.5 py-0.5 rounded-md uppercase tracking-wider">Master Unlocked</span>
                      </div>
                      <div className="text-[10px] text-slate-400 dark:text-slate-500 truncate">{googleUser.email}</div>
                    </div>
                    <button 
                      onClick={(e) => { e.stopPropagation(); handleGoogleSignOut(); }}
                      className="text-[10px] font-black text-red-500 hover:bg-red-500/10 px-2.5 py-1.5 rounded-lg transition-colors active:scale-95"
                    >
                      Sign Out
                    </button>
                  </div>
                ) : (
                  <>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleGoogleSignIn(); }}
                      disabled={isGoogleSigningIn}
                      className="w-full flex items-center justify-center gap-3 bg-white dark:bg-[#252528] hover:bg-slate-50 dark:hover:bg-[#2d2d31] border border-slate-200 dark:border-white/10 p-3 rounded-xl shadow-sm transition-all duration-200 active:scale-[0.98]"
                    >
                      {isGoogleSigningIn ? (
                        <Loader size={16} className="text-purple-500 animate-spin shrink-0" />
                      ) : (
                        <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
                          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                        </svg>
                      )}
                      <span className="text-xs font-black text-slate-700 dark:text-slate-200">
                        {isGoogleSigningIn ? (googleLoginDetail || 'Opening browser…') : 'Sign in with Google'}
                      </span>
                    </button>
                    {googleLoginDetail && !isGoogleSigningIn && (
                      <p className="text-[10px] text-center font-semibold text-red-500 dark:text-red-400 mt-1.5 animate-pulse">{googleLoginDetail}</p>
                    )}
                  </>
                )}


              </div>

              {/* Advanced Settings / Toggles */}
              <div className="px-4 py-3.5 border-b border-slate-100 dark:border-white/5 space-y-3 bg-slate-50/20 dark:bg-white/[0.01]">
                <div className="flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-[11px] font-black uppercase tracking-wider text-slate-700 dark:text-slate-200">Save as Draft</span>
                    <span className="text-[9px] text-slate-400 dark:text-slate-500 font-medium">Do not publish instantly</span>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); setSaveAsDraft(!saveAsDraft); }}
                    className={`w-9 h-5.5 flex items-center rounded-full p-0.5 transition-all duration-300 ${
                      saveAsDraft ? 'bg-gradient-to-r from-purple-500 to-pink-500' : 'bg-slate-200 dark:bg-zinc-700'
                    }`}
                  >
                    <div
                      className={`bg-white w-4.5 h-4.5 rounded-full shadow-sm transform transition-all duration-300 ${
                        saveAsDraft ? 'translate-x-3.5' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex flex-col">
                    <span className="text-[11px] font-black uppercase tracking-wider text-slate-700 dark:text-slate-200">Show Browser Window</span>
                    <span className="text-[9px] text-slate-400 dark:text-slate-500 font-medium">Watch automated upload live</span>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); setShowBrowser(!showBrowser); }}
                    className={`w-9 h-5.5 flex items-center rounded-full p-0.5 transition-all duration-300 ${
                      showBrowser ? 'bg-gradient-to-r from-purple-500 to-pink-500' : 'bg-slate-200 dark:bg-zinc-700'
                    }`}
                  >
                    <div
                      className={`bg-white w-4.5 h-4.5 rounded-full shadow-sm transform transition-all duration-300 ${
                        showBrowser ? 'translate-x-3.5' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>
              </div>

              {/* Platform list */}
              <div className="p-2 space-y-1">
                {PUBLISH_PLATFORMS.map(platform => {
                  const pStatus = getStatusForPlatform(platform.id);
                  const isPublished = pStatus?.status === 'PUBLISHED';
                  const isLoading = pStatus && !isPublished && pStatus.status !== 'ERROR';
                  const isError = pStatus?.status === 'ERROR';

                  return (
                    <button
                      key={platform.id}
                      onClick={(e) => { e.stopPropagation(); if (!isLoading && !isPublished) handlePublish(platform); }}
                      disabled={isLoading || isPublished}
                      className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group/pub ${
                        isPublished
                          ? 'bg-green-50 dark:bg-green-500/10 cursor-default'
                          : isLoading
                          ? 'bg-slate-50 dark:bg-white/5 cursor-wait'
                          : isError
                          ? 'bg-red-50 dark:bg-red-500/5 hover:bg-red-100 dark:hover:bg-red-500/10 cursor-pointer'
                          : 'hover:bg-slate-100 dark:hover:bg-white/8 cursor-pointer active:scale-[0.98]'
                      }`}
                    >
                      <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 text-lg" style={{ backgroundColor: platform.color + '15' }}>
                        {platform.icon}
                      </div>
                      <div className="flex-1 text-left min-w-0">
                        <div className="text-[13px] font-bold text-slate-800 dark:text-white flex items-center gap-2">
                          {platform.name}
                          <button 
                            onClick={(e) => { e.stopPropagation(); triggerExtensionSync(platform.id); }}
                            className="px-1.5 py-0.5 rounded bg-purple-500/10 hover:bg-purple-500/20 text-purple-600 dark:text-purple-400 text-[9px] font-bold uppercase tracking-wider transition-colors active:scale-95"
                            title={`Sync ${platform.name} cookies`}
                          >
                            ⚡ Sync
                          </button>
                        </div>
                        {pStatus ? (
                          <div className={`text-[10px] font-semibold truncate ${
                            isPublished ? 'text-green-600 dark:text-green-400'
                            : isError ? 'text-red-500 dark:text-red-400'
                            : 'text-purple-500 dark:text-purple-400'
                          }`}>
                            {pStatus.detail || pStatus.status}
                          </div>
                        ) : (
                          <div className="text-[10px] font-medium text-slate-400 dark:text-slate-500">
                            {googleUser ? "Master session linked" : "Ready to publish"}
                          </div>
                        )}
                      </div>
                      <div className="flex-shrink-0">
                        {isPublished ? (
                          <CheckCircle2 size={18} className="text-green-500" />
                        ) : isLoading ? (
                          <Loader size={18} className="text-purple-500 animate-spin" />
                        ) : isError ? (
                          <AlertCircle size={18} className="text-red-500" />
                        ) : (
                          <ChevronRight size={16} className="text-slate-300 dark:text-slate-600 group-hover/pub:text-purple-500 group-hover/pub:translate-x-0.5 transition-all" />
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Footer */}
              <div className="px-5 py-2.5 border-t border-slate-100 dark:border-white/10 bg-slate-50/50 dark:bg-white/[0.02]">
                <p className="text-[9px] text-slate-400 dark:text-slate-500 font-medium text-center leading-relaxed">
                  {googleUser 
                    ? "Signed in with Google Master Account • Unlocked"
                    : "First use opens browser for login • Saved locally"
                  }
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>


      </>,
      document.body
    )}
    </>
  );
};

const RangeSlider = ({ start, end, max, onChange, onSeek }) => {
  const startPerc = (start / max) * 100;
  const endPerc = (end / max) * 100;

  return (
    <div className="relative w-full h-12 flex items-center group">
      <div className="absolute w-full h-2 bg-slate-200 dark:bg-white/5 rounded-full overflow-hidden">
        <div
          className="absolute h-full bg-gradient-to-r from-yt-red to-tk-pink opacity-40"
          style={{ left: `${startPerc}%`, width: `${endPerc - startPerc}%` }}
        />
      </div>
      <input
        type="range"
        min="0"
        max={max}
        step="0.1"
        value={start}
        onChange={(e) => {
          const val = Math.min(parseFloat(e.target.value), end - 0.5);
          onChange(val, end);
        }}
        onMouseDown={() => onSeek(start)}
        className="absolute w-full h-2 bg-transparent appearance-none pointer-events-none cursor-pointer z-20 [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-yt-red"
      />
      <input
        type="range"
        min="0"
        max={max}
        step="0.1"
        value={end}
        onChange={(e) => {
          const val = Math.max(parseFloat(e.target.value), start + 0.5);
          onChange(start, val);
        }}
        onMouseDown={() => onSeek(end)}
        className="absolute w-full h-2 bg-transparent appearance-none pointer-events-none cursor-pointer z-20 [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-tk-pink"
      />
      <div className="absolute -bottom-1 w-full flex justify-between px-1">
        <span className="text-[9px] font-black text-yt-red/60">{start.toFixed(1)}s</span>
        <span className="text-[9px] font-black text-tk-pink/60">{end.toFixed(1)}s</span>
      </div>
    </div>
  );
};

const PremiumSelect = ({ label, value, options, onChange, icon: Icon, color, isActive }) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const selectedOption = options.find(opt => (opt.id || opt) === value) || (options.length > 0 ? options[0] : null);

  return (
    <div className="relative space-y-3" ref={dropdownRef}>
      <div className="flex items-center justify-between px-1">
        <label className="text-[11px] font-black uppercase tracking-[0.15em] text-slate-400 dark:text-slate-300 flex items-center gap-2">
          <Icon size={14} className={color} />
          {label}
        </label>
        {isActive && (
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-yt-red opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-yt-red"></span>
          </span>
        )}
      </div>

      <div className="relative">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full h-14 bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-2xl px-5 flex items-center justify-between group hover:border-yt-red/30 transition-all shadow-sm"
        >
          <div className="flex flex-col items-start gap-0.5">
            <span className="text-[13px] font-bold text-slate-900 dark:text-white">
              {selectedOption ? (typeof selectedOption === 'string' ? selectedOption : selectedOption?.name) : 'Select...'}
            </span>
            {selectedOption?.id && (
              <span className="text-[9px] font-mono bg-slate-200 dark:bg-white/10 text-slate-700 dark:text-slate-300 px-2 py-0.5 rounded">
                {selectedOption.id}
              </span>
            )}
            {selectedOption?.desc && (
              <span className="text-[10px] text-slate-500 dark:text-slate-300 font-medium line-clamp-1">
                {selectedOption.desc}
              </span>
            )}
          </div>
          <ChevronDown size={18} className={`text-slate-400 group-hover:text-yt-red transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        <AnimatePresence>
          {isOpen && options.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              className="absolute top-full mt-3 w-full bg-white dark:bg-[#1a1a1a] border border-slate-200 dark:border-white/10 rounded-[22px] shadow-2xl z-[200] overflow-hidden"
            >
              <div className="p-2 max-h-[360px] overflow-y-auto custom-scrollbar">
                {options.map((opt) => {
                  const id = opt.id || opt;
                  const name = opt.name || opt;
                  const isSelected = id === value;

                  return (
                    <button
                      key={id}
                      onClick={() => { onChange(id); setIsOpen(false); }}
                      className={`w-full p-4 rounded-xl flex flex-col items-start gap-2 transition-all ${isSelected ? 'bg-yt-red/10 border border-yt-red/20' : 'hover:bg-slate-50 dark:hover:bg-white/5'}`}
                    >
                      <div className="flex items-center justify-between w-full gap-2">
                        <span className={`text-[12px] font-bold ${isSelected ? 'text-yt-red' : 'text-slate-700 dark:text-slate-200'}`}>{name}</span>
                        {isSelected && <Check size={14} className="text-yt-red" />}
                      </div>
                      {id && <span className="text-[8px] font-mono bg-slate-200 dark:bg-white/10 text-slate-700 dark:text-slate-300 px-2 py-1 rounded max-w-full break-all">{id}</span>}
                      {opt.desc && <span className="text-[10px] text-slate-500 dark:text-slate-300 text-left leading-relaxed">{opt.desc}</span>}
                    </button>
                  );
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

const ReviewPortal = ({ sessionId, onCommit, isDark }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [committing, setCommitting] = useState(false);
  const [totalDuration, setTotalDuration] = useState(0);
  const audioRef = useRef(null);
  const [playingIdx, setPlayingIdx] = useState(null);

  useEffect(() => {
    const fetchReviewData = async () => {
      try {
        const res = await axios.get(`${API_BASE}/review/${sessionId}`);
        setData(res.data);
      } catch (err) {
        console.error("Failed to fetch review data", err);
      } finally {
        setLoading(false);
      }
    };
    fetchReviewData();
  }, [sessionId]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const handleTimeUpdate = () => {
      if (playingIdx !== null && data?.semantics) {
        const currentStanza = data.semantics[playingIdx];
        if (audio.currentTime >= currentStanza.end_time) {
          audio.pause();
          setPlayingIdx(null);
        }
      }
    };
    audio.addEventListener('timeupdate', handleTimeUpdate);
    return () => audio.removeEventListener('timeupdate', handleTimeUpdate);
  }, [playingIdx, data]);

  const togglePlayStanza = (idx) => {
    if (!audioRef.current) return;
    if (playingIdx === idx) {
      audioRef.current.pause();
      setPlayingIdx(null);
    } else {
      const stanza = data.semantics[idx];
      audioRef.current.currentTime = stanza.start_time;
      audioRef.current.play();
      setPlayingIdx(idx);
    }
  };

  const getLyricsForRange = (start, end) => {
    if (!data || !data.transcript || !data.transcript.segments) return "";
    let lyrics = [];
    data.transcript.segments.forEach(seg => {
      if (seg.words) {
        seg.words.forEach(w => {
          if (w.start < end && w.end > start) lyrics.push(w.word.trim());
        });
      } else {
        if (seg.start < end && seg.end > start) lyrics.push(seg.text.trim());
      }
    });
    return lyrics.join(" ");
  };

  const handleUpdateStanza = (idx, field, value) => {
    const newData = { ...data };
    newData.semantics[idx][field] = value;

    // Flag that the user has manually touched this text box
    if (field === 'text') {
      newData.semantics[idx].manually_edited = true;
    }

    setData(newData);
  };

  const handleSliderChange = (idx, start, end) => {
    if (!data || !data.semantics) return;
    const newSemantics = [...data.semantics];
    const transcript = data.transcript;
    const currentStanza = newSemantics[idx];

    // Helper function to safely fetch words from the original AI transcript for a specific time range
    const getWordsInTimeframe = (t_start, t_end) => {
      if (t_start >= t_end) return [];
      let lyrics = [];
      if (transcript && transcript.segments) {
        transcript.segments.forEach(seg => {
          if (seg.words) {
            seg.words.forEach(w => {
              if (w.start < t_end && w.end > t_start) lyrics.push(w.word.trim());
            });
          } else if (seg.start < t_end && seg.end > t_start) {
            lyrics.push(seg.text.trim());
          }
        });
      }
      return lyrics;
    };

    let currentText = currentStanza.text || "";

    if (currentStanza.manually_edited) {
      // THE SMART DELTA MERGE: 
      // If the user made spelling edits, we don't overwrite them. Instead, we add or remove 
      // transcript words at the edges of the sentence based on how the slider was moved!
      const oldStart = currentStanza.start_time;
      const oldEnd = currentStanza.end_time;

      const addedToFront = getWordsInTimeframe(start, oldStart);
      const addedToEnd = getWordsInTimeframe(oldEnd, end);
      const removedFromFront = getWordsInTimeframe(oldStart, start);
      const removedFromEnd = getWordsInTimeframe(end, oldEnd);

      let userWords = currentText.split(/\s+/).filter(Boolean);

      // Remove words from the boundaries if slider shrank
      if (removedFromFront.length > 0) userWords.splice(0, removedFromFront.length);
      if (removedFromEnd.length > 0) userWords.splice(userWords.length - removedFromEnd.length, removedFromEnd.length);

      // Append words to the boundaries if slider expanded
      if (addedToFront.length > 0) userWords = [...addedToFront, ...userWords];
      if (addedToEnd.length > 0) userWords = [...userWords, ...addedToEnd];

      currentText = userWords.join(" ");
    } else {
      // If no manual edits have been made yet, just load the transcript dynamically as normal
      const newWords = getWordsInTimeframe(start, end);
      currentText = newWords.join(" ");
    }

    newSemantics[idx] = { ...currentStanza, start_time: start, end_time: end, text: currentText };
    setData({ ...data, semantics: newSemantics });
  };

  const handleAddStanza = () => {
    const lastStanza = data.semantics[data.semantics.length - 1];
    const newStart = lastStanza ? lastStanza.end_time : 0;
    const newEnd = lastStanza ? lastStanza.end_time + 10 : 10;
    const newStanza = {
      title: "New Segment",
      start_time: newStart,
      end_time: newEnd,
      visual_queries: ["cinematic close up", "dramatic lighting"],
      text: getLyricsForRange(newStart, newEnd) || "New lyrics here...",
      manually_edited: false
    };
    setData({ ...data, semantics: [...data.semantics, newStanza] });
  };

  const handleRemoveStanza = (idx) => {
    const newData = { ...data, semantics: data.semantics.filter((_, i) => i !== idx) };
    setData(newData);
  };

  const handleFinalize = async () => {
    setCommitting(true);
    try {
      await axios.post(`${API_BASE}/review/${sessionId}/commit`, { semantics: data.semantics });
      onCommit();
    } catch (err) {
      console.error("Commit failed", err);
      setCommitting(false);
    }
  };

  const seekAudio = (time) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      audioRef.current.play();
    }
  };

  if (loading) return (
    <div className="flex flex-col items-center justify-center p-20 space-y-4">
      <div className="w-12 h-12 border-4 border-yt-red border-t-transparent rounded-full animate-spin"></div>
      <p className="text-slate-500 dark:text-slate-300 font-black uppercase tracking-widest text-xs">Loading AI Analysis...</p>
    </div>
  );

  if (!data || !data.semantics) return (
    <div className="flex flex-col items-center justify-center p-20 space-y-6 glass-card bg-red-500/5 border-red-500/20">
      <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center text-red-500"><AlertCircle size={32} /></div>
      <div className="text-center">
        <h3 className="text-xl font-black text-slate-900 dark:text-white uppercase tracking-tight">Analysis Sync Failed</h3>
        <p className="text-slate-500 dark:text-slate-300 font-bold max-w-xs mx-auto">The AI semantic data could not be retrieved. Please check the backend logs.</p>
      </div>
      <button onClick={() => window.location.reload()} className="px-6 py-2 bg-slate-200 dark:bg-white/10 rounded-xl font-black uppercase tracking-widest text-[10px] hover:bg-slate-300 transition-all">Retry Sync</button>
    </div>
  );

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row items-center justify-between gap-6">
        <div>
          <h2 className="text-4xl font-black text-slate-900 dark:text-white uppercase tracking-tight">Studio Review Gate</h2>
          <p className="text-slate-500 dark:text-slate-300 font-bold">Refine stanzas and lyrics before high-precision rendering.</p>
        </div>
        <div className="flex items-center gap-4">
          <button onClick={handleFinalize} disabled={committing} className="btn-primary flex items-center gap-3 px-8 py-4 shadow-[0_20px_40px_rgba(255,0,0,0.3)]">
            {committing ? <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div> : <Save size={20} />}
            <span className="font-black uppercase tracking-wider text-lg">Finalize Production</span>
          </button>
        </div>
      </div>

      <audio ref={audioRef} onLoadedMetadata={(e) => setTotalDuration(e.target.duration)} src={`${API_BASE}/temp/session_${sessionId}/source_audio.wav`} className="hidden" />

      <div className="grid grid-cols-1 gap-6 pb-20">
        {data.semantics.map((stanza, idx) => (
          <motion.div key={idx} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: idx * 0.05 }} className={`glass-card p-8 group relative overflow-hidden border-white/10 transition-all duration-500 ${playingIdx === idx ? 'border-yt-red/50 ring-1 ring-yt-red/20 shadow-[0_0_30px_rgba(255,0,0,0.1)]' : 'hover:border-yt-red/30'}`}>
            <div className={`absolute top-0 left-0 w-1.5 h-full bg-gradient-to-b from-yt-red to-tk-pink transition-opacity duration-500 ${playingIdx === idx ? 'opacity-100' : 'opacity-40 group-hover:opacity-100'}`}></div>
            <div className="flex flex-col lg:flex-row gap-8">
              <div className="flex-1 space-y-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <button onClick={() => togglePlayStanza(idx)} className={`w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-300 shadow-lg active:scale-90 ${playingIdx === idx ? 'bg-yt-red text-white' : 'bg-yt-red/10 text-yt-red hover:bg-yt-red hover:text-white'}`}>
                      {playingIdx === idx ? <Pause size={24} fill="currentColor" /> : <Play size={24} className="ml-1" fill="currentColor" />}
                    </button>
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">Precision Slicing</span>
                        {playingIdx === idx && (
                          <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-yt-red/10 text-yt-red text-[8px] font-black uppercase animate-pulse">
                            <div className="w-1 h-1 rounded-full bg-yt-red"></div> Live
                          </span>
                        )}
                      </div>
                      <div className="w-64">
                        <RangeSlider max={totalDuration || 300} start={stanza.start_time} end={stanza.end_time} onSeek={seekAudio} onChange={(s, e) => handleSliderChange(idx, s, e)} />
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <button onClick={() => handleRemoveStanza(idx)} className="p-2.5 text-slate-400 hover:text-yt-red hover:bg-yt-red/10 rounded-xl transition-all"><Trash2 size={20} /></button>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-500 dark:text-slate-300">Cinematic Lyrics (ASS Target)</label>
                    <span className={`text-[10px] font-bold uppercase tracking-widest italic transition-colors ${stanza.manually_edited ? 'text-emerald-500' : 'text-yt-red/50'}`}>
                      {stanza.manually_edited ? 'Manual Edit Saved' : 'User Correction Required'}
                    </span>
                  </div>

                  <textarea
                    dir="rtl"
                    value={stanza.text}
                    onChange={(e) => handleUpdateStanza(idx, 'text', e.target.value)}
                    placeholder="Enter the extracted lyrics here for precise subtitle mapping..."
                    className="w-full bg-slate-50 dark:bg-black/60 border border-slate-200 dark:border-white/10 rounded-2xl p-6 text-xl font-bold text-slate-700 dark:text-slate-100 leading-relaxed focus:border-yt-red/50 focus:ring-4 focus:ring-yt-red/5 transition-all min-h-[140px] custom-scrollbar placeholder:text-slate-300 dark:placeholder:text-slate-500 text-right"
                  />

                  <div className="pt-4 flex items-center gap-3 border-t border-slate-200 dark:border-white/5">
                    <Edit3 size={14} className="text-yt-red" />
                    <input type="text" dir="auto" value={stanza.title} onChange={(e) => handleUpdateStanza(idx, 'title', e.target.value)} className="bg-transparent border-none outline-none text-sm font-black text-slate-900 dark:text-white w-full focus:text-yt-red transition-colors placeholder:text-slate-400" placeholder="Poetic Stanza Name (e.g. Intro Verse)..." />
                  </div>
                </div>
              </div>

              <div className="w-full lg:w-80 space-y-4">
                <label className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-500 dark:text-slate-300">AI Visual Concepts</label>
                <div className="space-y-3">
                  {(stanza.visual_queries || []).map((query, qIdx) => (
                    <div key={qIdx} className="flex items-center gap-3 bg-slate-100 dark:bg-white/5 px-5 py-3 rounded-xl border border-slate-200 dark:border-white/10 group/item hover:border-yt-red/20 transition-all">
                      <Sparkles size={14} className="text-yellow-500 shrink-0" />
                      <input type="text" value={query} onChange={(e) => { const newQueries = [...stanza.visual_queries]; newQueries[qIdx] = e.target.value; handleUpdateStanza(idx, 'visual_queries', newQueries); }} className="bg-transparent border-none outline-none text-xs font-bold text-slate-600 dark:text-slate-200 w-full" />
                    </div>
                  ))}
                  <button onClick={() => { const newQueries = [...(stanza.visual_queries || []), "new cinematic query"]; handleUpdateStanza(idx, 'visual_queries', newQueries); }} className="w-full flex items-center justify-center gap-2 py-3 border border-dashed border-slate-300 dark:border-white/10 rounded-xl text-[10px] font-black text-slate-400 hover:border-yt-red hover:text-yt-red hover:bg-yt-red/5 transition-all">
                    <Plus size={14} /> Add Concept Query
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
        <button onClick={handleAddStanza} className="w-full py-12 border-2 border-dashed border-slate-300 dark:border-white/10 rounded-[40px] flex flex-col items-center justify-center gap-4 text-slate-400 hover:border-yt-red hover:text-yt-red hover:bg-yt-red/5 transition-all group shadow-sm hover:shadow-xl">
          <div className="w-16 h-16 rounded-full bg-slate-100 dark:bg-white/5 flex items-center justify-center group-hover:scale-110 transition-transform shadow-inner"><Plus size={32} /></div>
          <div className="flex flex-col items-center gap-1">
            <span className="font-black uppercase tracking-[0.3em] text-sm">Add Precision Segment</span>
            <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest">Manually slice a new stanza</span>
          </div>
        </button>
      </div>
    </motion.div>
  );
};

function App() {
  const [mode, setMode] = useState(localStorage.getItem('utik_mode') || 'clip');
  const [url, setUrl] = useState(localStorage.getItem('utik_url') || '');
  const [promptText, setPromptText] = useState(localStorage.getItem('utik_prompt_text') || '');
  const [selectedGenres, setSelectedGenres] = useState(JSON.parse(localStorage.getItem('utik_genres') || '[]'));
  const [songName, setSongName] = useState(localStorage.getItem('utik_song_name') || '');
  const [artistName, setArtistName] = useState(localStorage.getItem('utik_artist_name') || '');
  const [targetDuration, setTargetDuration] = useState(Number(localStorage.getItem('utik_target_duration')) || 30);
  const [sessionId, setSessionId] = useState(localStorage.getItem('utik_session_id') || null);
  const [status, setStatus] = useState(localStorage.getItem('utik_status') || 'IDLE');
  const [progress, setProgress] = useState(Number(localStorage.getItem('utik_progress')) || 0);
  const [logs, setLogs] = useState(JSON.parse(localStorage.getItem('utik_logs') || '[]'));
  const [results, setResults] = useState(JSON.parse(localStorage.getItem('utik_results') || '[]'));
  const [processResponse, setProcessResponse] = useState(null);
  const [lastPoll, setLastPoll] = useState(null);
  const [activeTab, setActiveTab] = useState(localStorage.getItem('utik_active_tab') || 'studio');
  const [isDark, setIsDark] = useState(localStorage.getItem('utik_dark') === 'true');
  const [showSettings, setShowSettings] = useState(false);
  const [selectedModel, setSelectedModel] = useState(localStorage.getItem('utik_whisper_model') || 'x-large-v3-turbo');
  const [selectedStyle, setSelectedStyle] = useState(localStorage.getItem('utik_style') || 'TikTok');
  const [selectedGoogleModel, setSelectedGoogleModel] = useState(localStorage.getItem('utik_google_model') || 'models/gemma-4-31b-it');
  const [selectedTTSEngine, setSelectedTTSEngine] = useState(localStorage.getItem('utik_tts_engine') || 'supertonic');
  const [selectedTTSVoice, setSelectedTTSVoice] = useState(localStorage.getItem('utik_tts_voice') || 'M1');
  const [manualReview, setManualReview] = useState(localStorage.getItem('utik_manual_review') === 'true');
  const [activeVncJobId, setActiveVncJobId] = useState(null);

  // Google Master Auth State (shared across landing page + publish panel)
  const [googleUser, setGoogleUser] = useState(null);
  const [isGoogleSigningIn, setIsGoogleSigningIn] = useState(false);
  const [googleLoginDetail, setGoogleLoginDetail] = useState('');
  const [syncingExtension, setSyncingExtension] = useState(false);
  const [syncResultMsg, setSyncResultMsg] = useState('');
  const [showSyncGuideModal, setShowSyncGuideModal] = useState(false);
  const [pastedCookies, setPastedCookies] = useState("");
  const [extensionActive, setExtensionActive] = useState(false);

  // Direct Landing Page Cookies State
  const [directPastedCookies, setDirectPastedCookies] = useState("");
  const [directSyncing, setDirectSyncing] = useState(false);
  const [directSyncResultMsg, setDirectSyncResultMsg] = useState("");

  const handleDirectCookiesSync = async () => {
    if (!directPastedCookies.trim()) return;
    setDirectSyncing(true);
    setDirectSyncResultMsg("Syncing YouTube cookies...");
    try {
      const res = await axios.post(`${API_BASE}/auth/youtube/cookies`, {
        cookies: directPastedCookies
      });
      if (res.data && res.data.status === "success") {
        setDirectSyncResultMsg("🎉 YouTube cookies successfully synced to backend!");
        setDirectPastedCookies("");
      } else {
        setDirectSyncResultMsg("❌ Cloud rejected cookies.");
      }
    } catch (err) {
      console.error(err);
      setDirectSyncResultMsg("❌ Sync failed: Connection error.");
    } finally {
      setDirectSyncing(false);
      setTimeout(() => setDirectSyncResultMsg(""), 8000);
    }
  };

  // Check if extension is active while modal is open (fast polling)
  useEffect(() => {
    if (!showSyncGuideModal) return;
    
    setExtensionActive(!!window.__YOUTIK_SYNC_EXTENSION__);
    
    const handleExtensionPong = (event) => {
      if (event.source !== window || !event.data) return;
      if (event.data.type === "YOUTIK_PONG") {
        window.__YOUTIK_SYNC_EXTENSION__ = true;
        setExtensionActive(true);
      }
    };
    
    window.addEventListener("message", handleExtensionPong);
    
    // Poll and ping extension
    const interval = setInterval(() => {
      window.postMessage({ type: "YOUTIK_PING" }, "*");
      if (window.__YOUTIK_SYNC_EXTENSION__) {
        setExtensionActive(true);
      }
    }, 1000);
    
    // Initial ping
    window.postMessage({ type: "YOUTIK_PING" }, "*");
    
    return () => {
      window.removeEventListener("message", handleExtensionPong);
      clearInterval(interval);
    };
  }, [showSyncGuideModal]);

  // Global background check for extension active status
  useEffect(() => {
    const handleExtensionPongGlobal = (event) => {
      if (event.source !== window || !event.data) return;
      if (event.data.type === "YOUTIK_PONG") {
        window.__YOUTIK_SYNC_EXTENSION__ = true;
      }
    };
    
    window.addEventListener("message", handleExtensionPongGlobal);
    
    // Ping every 3 seconds globally
    const interval = setInterval(() => {
      window.postMessage({ type: "YOUTIK_PING" }, "*");
    }, 3000);
    
    // Initial ping
    window.postMessage({ type: "YOUTIK_PING" }, "*");
    
    return () => {
      window.removeEventListener("message", handleExtensionPongGlobal);
      clearInterval(interval);
    };
  }, []);

  // Sync state values to localStorage
  useEffect(() => {
    localStorage.setItem('utik_mode', mode);
  }, [mode]);

  useEffect(() => {
    localStorage.setItem('utik_url', url);
  }, [url]);

  useEffect(() => {
    localStorage.setItem('utik_prompt_text', promptText);
  }, [promptText]);

  useEffect(() => {
    localStorage.setItem('utik_genres', JSON.stringify(selectedGenres));
  }, [selectedGenres]);

  useEffect(() => {
    localStorage.setItem('utik_song_name', songName);
  }, [songName]);

  useEffect(() => {
    localStorage.setItem('utik_artist_name', artistName);
  }, [artistName]);

  useEffect(() => {
    localStorage.setItem('utik_target_duration', targetDuration);
  }, [targetDuration]);

  useEffect(() => {
    if (sessionId) localStorage.setItem('utik_session_id', sessionId);
    else localStorage.removeItem('utik_session_id');
  }, [sessionId]);

  useEffect(() => {
    localStorage.setItem('utik_status', status);
  }, [status]);

  useEffect(() => {
    localStorage.setItem('utik_progress', progress);
  }, [progress]);

  useEffect(() => {
    localStorage.setItem('utik_logs', JSON.stringify(logs));
  }, [logs]);

  useEffect(() => {
    localStorage.setItem('utik_results', JSON.stringify(results));
  }, [results]);

  useEffect(() => {
    localStorage.setItem('utik_active_tab', activeTab);
  }, [activeTab]);

  useEffect(() => {
    localStorage.setItem('utik_dark', isDark);
  }, [isDark]);

  useEffect(() => {
    localStorage.setItem('utik_manual_review', manualReview);
  }, [manualReview]);

  // Fetch Google Master user on mount
  useEffect(() => {
    const fetchGoogleUser = async () => {
      try {
        const res = await axios.get(`${API_BASE}/auth/google/user`);
        if (res.data) setGoogleUser(res.data);
      } catch (err) {
        console.warn("Could not fetch Google user", err);
      }
    };
    fetchGoogleUser();
  }, []);

  // App-level Google Sign-In handler (shared with landing page + publish panel)
  const handleGoogleSignIn = async () => {
    setIsGoogleSigningIn(true);
    setGoogleLoginDetail('Opening browser…');
    try {
      const res = await axios.post(`${API_BASE}/auth/google`);
      const jobId = res.data.job_id;

      const poll = setInterval(async () => {
        try {
          const statusRes = await axios.get(`${API_BASE}/auth/google/status/${jobId}`);
          const { status: st, detail, user, vnc_active } = statusRes.data;
          setGoogleLoginDetail(detail || st);

          if (vnc_active) {
            setActiveVncJobId(jobId);
          }

          if (st === 'AUTHENTICATED') {
            clearInterval(poll);
            const userRes = await axios.get(`${API_BASE}/auth/google/user`);
            if (userRes.data) {
              setGoogleUser(userRes.data);
            }
            setIsGoogleSigningIn(false);
            setGoogleLoginDetail('');
          } else if (st === 'ERROR' || st === 'TIMEOUT') {
            clearInterval(poll);
            setIsGoogleSigningIn(false);
            setTimeout(() => setGoogleLoginDetail(''), 8000);
          }
        } catch {
          clearInterval(poll);
          setIsGoogleSigningIn(false);
          setGoogleLoginDetail('');
        }
      }, 2000);
    } catch (err) {
      console.error("Google auth failed", err);
      setIsGoogleSigningIn(false);
      setGoogleLoginDetail('Failed to start login');
      setTimeout(() => setGoogleLoginDetail(''), 5000);
    }
  };

  const [syncPlatform, setSyncPlatform] = useState('youtube');

  const triggerExtensionSync = (platform = 'youtube') => {
    setSyncPlatform(platform);
    if (!window.__YOUTIK_SYNC_EXTENSION__) {
      setShowSyncGuideModal(true);
      return;
    }
    
    setSyncingExtension(true);
    setSyncResultMsg(`Requesting ${platform} session cookies...`);
    
    const handleSyncResponse = async (event) => {
      if (event.source !== window || !event.data || event.data.type !== "YOUTIK_SYNC_RESULT") return;
      
      window.removeEventListener("message", handleSyncResponse);
      
      const { success, cookies, error, platform: responsePlatform } = event.data;
      const targetPlatform = responsePlatform || platform;
      
      if (!success) {
        setSyncResultMsg(`Sync failed: ${error || `Verify you are signed into ${targetPlatform}!`}`);
        setSyncingExtension(false);
        setTimeout(() => setSyncResultMsg(""), 8000);
        return;
      }
      
      try {
        setSyncResultMsg("Syncing session with cloud backend...");
        const res = await axios.post(`${API_BASE}/api/auth/cookies/sync`, {
          user_id: "default",
          platform: targetPlatform,
          cookies: typeof cookies === 'string' ? JSON.parse(cookies) : cookies
        });
        
        if (res.data && res.data.status === "success") {
          setSyncResultMsg(`🎉 ${targetPlatform} session successfully synced!`);
          // Fetch synced google user info to update UI
          const userRes = await axios.get(`${API_BASE}/auth/google/user`);
          if (userRes.data) {
            setGoogleUser(userRes.data);
          }
        } else {
          setSyncResultMsg("Cloud rejected cookies session.");
        }
      } catch (err) {
        console.error("Backend cookies sync failed", err);
        setSyncResultMsg("Sync failed: Backend connection error.");
      } finally {
        setSyncingExtension(false);
        setTimeout(() => setSyncResultMsg(""), 8000);
      }
    };
    
    window.addEventListener("message", handleSyncResponse);
    
    // Trigger Content Script injection message
    window.postMessage({ type: "YOUTIK_TRIGGER_SYNC", platform: platform }, "*");
  };

  const handleCookieFileUpload = (event) => {
    const file = event.target.files[0];
    if (!file) return;
    
    setSyncingExtension(true);
    setSyncResultMsg("Reading cookie file...");
    
    const reader = new FileReader();
    reader.onload = async (e) => {
      const content = e.target.result;
      try {
        setSyncResultMsg("Syncing uploaded cookies with cloud backend...");
        const res = await axios.post(`${API_BASE}/api/auth/cookies/sync`, {
          user_id: "default",
          platform: syncPlatform,
          cookies: JSON.parse(content)
        });
        
        if (res.data && res.data.status === "success") {
          setSyncResultMsg(`🎉 ${syncPlatform} cookies successfully synced from file!`);
          // Fetch synced google user info to update UI
          const userRes = await axios.get(`${API_BASE}/auth/google/user`);
          if (userRes.data) {
            setGoogleUser(userRes.data);
          }
        } else {
          setSyncResultMsg("Cloud rejected uploaded cookies.");
        }
      } catch (err) {
        console.error("Cookie file upload failed", err);
        setSyncResultMsg("Sync failed: Backend connection error.");
      } finally {
        setSyncingExtension(false);
        setTimeout(() => setSyncResultMsg(""), 8000);
      }
    };
    reader.readAsText(file);
  };

  const handlePastedCookiesSync = async () => {
    if (!pastedCookies.trim()) return;
    
    setSyncingExtension(true);
    setSyncResultMsg("Syncing pasted cookies with cloud backend...");
    
    try {
      const res = await axios.post(`${API_BASE}/api/auth/cookies/sync`, {
        user_id: "default",
        platform: syncPlatform,
        cookies: JSON.parse(pastedCookies)
      });
      
      if (res.data && res.data.status === "success") {
        setSyncResultMsg(`🎉 ${syncPlatform} cookies successfully synced from paste!`);
        setPastedCookies("");
        setShowSyncGuideModal(false);
        // Fetch synced google user info to update UI
        const userRes = await axios.get(`${API_BASE}/auth/google/user`);
        if (userRes.data) {
          setGoogleUser(userRes.data);
        }
      } else {
        setSyncResultMsg("Cloud rejected pasted cookies.");
      }
    } catch (err) {
      console.error("Pasted cookies sync failed", err);
      setSyncResultMsg("Sync failed: Backend connection error.");
    } finally {
      setSyncingExtension(false);
      setTimeout(() => setSyncResultMsg(""), 8000);
    }
  };

  const handleGoogleSignOut = async () => {
    try {
      await axios.post(`${API_BASE}/auth/google/logout`);
      setGoogleUser(null);
    } catch (err) {
      console.error("Google Master SignOut failed", err);
    }
  };

  const handleResetSession = async () => {
    try {
      await axios.post(`${API_BASE}/api/reset`);
      // Clear localStorage
      localStorage.removeItem('utik_session_id');
      localStorage.removeItem('utik_status');
      localStorage.removeItem('utik_progress');
      localStorage.removeItem('utik_results');
      localStorage.removeItem('utik_logs');
      localStorage.removeItem('utik_url');
      localStorage.removeItem('utik_prompt_text');
      localStorage.removeItem('utik_genres');
      localStorage.removeItem('utik_song_name');
      localStorage.removeItem('utik_artist_name');
      localStorage.removeItem('utik_target_duration');
      
      // Reset state
      setSessionId(null);
      setStatus('IDLE');
      setProgress(0);
      setResults([]);
      setLogs([]);
      setProcessResponse(null);
      setActiveTab('studio');
      setPromptText('');
      setUrl('');
      setSelectedGenres([]);
      setSongName('');
      setArtistName('');
      setTargetDuration(30);
    } catch (err) {
      console.error("Failed to reset session", err);
    }
  };

  const steps = mode === 'create' ? createSteps : (manualReview ? clipSteps : clipSteps.filter(s => s.id !== 'WAITING_FOR_REVIEW'));
  const [availableModels, setAvailableModels] = useState([]);
  const [googleModels, setGoogleModels] = useState([]);
  const [ttsEngines, setTtsEngines] = useState([]);
  const [ttsVoices, setTtsVoices] = useState([]);
  const [subtitleStyles, setSubtitleStyles] = useState(["TikTok", "Cinematic", "Dynamic", "Glow", "Box"]);

  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const res = await axios.get(`${API_BASE}/config`);
        if (res.data.models) setAvailableModels(res.data.models);
        if (res.data.google_models) {
          setGoogleModels(res.data.google_models);
          if (!localStorage.getItem('utik_google_model')) setSelectedGoogleModel(res.data.google_models[0].id);
        }
        if (res.data.subtitle_styles) setSubtitleStyles(res.data.subtitle_styles);
        if (res.data.tts_engines) setTtsEngines(res.data.tts_engines);
        if (res.data.tts_voices) setTtsVoices(res.data.tts_voices);
      } catch (err) {
        console.warn("Could not fetch config", err);
      }
    };
    fetchConfig();
  }, []);

  useEffect(() => {
    localStorage.setItem('utik_whisper_model', selectedModel);
    localStorage.setItem('utik_style', selectedStyle);
    localStorage.setItem('utik_google_model', selectedGoogleModel);
    localStorage.setItem('utik_tts_engine', selectedTTSEngine);
    localStorage.setItem('utik_tts_voice', selectedTTSVoice);
  }, [selectedModel, selectedStyle, selectedGoogleModel, selectedTTSEngine, selectedTTSVoice]);

  useEffect(() => { window.scrollTo(0, 0); }, []);
  useEffect(() => { isDark ? document.documentElement.classList.add('dark') : document.documentElement.classList.remove('dark'); }, [isDark]);

  useEffect(() => {
    if (!sessionId) return;

    let isPolling = true;

    const fetchStatus = async () => {
      if (!isPolling) return;
      try {
        const res = await axios.get(`${API_BASE}/status/${sessionId}`);
        setLastPoll(res.data);
        setStatus(res.data.status);
        setLogs(res.data.logs);
        setResults(res.data.clips || []);

        const currentSteps = mode === 'create' ? createSteps : (manualReview ? clipSteps : clipSteps.filter(s => s.id !== 'WAITING_FOR_REVIEW'));
        const stepIndex = currentSteps.findIndex(s => s.id === res.data.status);

        if (stepIndex !== -1) {
          setProgress(((stepIndex + 1) / currentSteps.length) * 100);
        } else {
          const fallback = statusProgressMap[res.data.status];
          if (fallback !== undefined) setProgress(fallback);
          else if (res.data.status === 'COMPLETED') setProgress(100);
        }

        if (res.data.status === 'COMPLETED' || res.data.status === 'ERROR') {
          isPolling = false;
        }
      } catch (err) {
        if (err.response && err.response.status === 404) {
          isPolling = false;
          setSessionId(null);
          localStorage.removeItem('utik_session_id');
          localStorage.removeItem('utik_status');
          localStorage.removeItem('utik_progress');
          localStorage.removeItem('utik_results');
          localStorage.removeItem('utik_logs');
          setStatus('IDLE');
          setProgress(0);
          setResults([]);
          setLogs([]);
        } else {
          console.error("Polling failed", err);
        }
      }
    };

    fetchStatus();
    const interval = setInterval(() => {
      if (isPolling) fetchStatus();
      else clearInterval(interval);
    }, 1500);

    return () => {
      isPolling = false;
      clearInterval(interval);
    };
  }, [sessionId, mode, manualReview]);

  const handleSwitchMode = async (newMode) => {
    if (newMode === mode) return;

    if (newMode === 'create' && sessionId && (status === 'WAITING_FOR_REVIEW' || status === 'COMPLETED')) {
      try {
        const res = await axios.get(`${API_BASE}/review/${sessionId}`);
        if (res.data && res.data.semantics) {
          const lyrics = res.data.semantics.map(s => s.text).join('\n\n');
          setPromptText(lyrics);
        } else if (res.data && res.data.full_text) {
          setPromptText(res.data.full_text);
        }
      } catch (e) {
        console.log("Could not load previous lyrics");
      }
    }

    setMode(newMode);

    if (status === 'WAITING_FOR_REVIEW' || status === 'COMPLETED' || status === 'ERROR') {
      setStatus('IDLE');
      setProgress(0);
      setSessionId(null);
    }
  };

  const toggleGenre = (genre) => {
    setSelectedGenres(prev => prev.includes(genre) ? prev.filter(g => g !== genre) : [...prev, genre]);
  };

  const handleStart = async () => {
    if (mode === 'clip' && !url) return;
    if (mode === 'create' && !promptText) return;

    setLogs(["[SYSTEM] Initializing production pipeline..."]);
    setStatus('STARTING');
    setProgress(0);
    setResults([]);
    setProcessResponse(null);
    try {
      const res = await axios.post(`${API_BASE}/process`, {
        mode,
        url,
        prompt: promptText,
        mixed_genres: selectedGenres.join(", "),
        model_id: selectedModel,
        subtitle_style: selectedStyle,
        google_model: selectedGoogleModel,
        tts_engine: selectedTTSEngine,
        tts_voice: selectedTTSVoice,
        song_name: songName,
        artist_name: artistName,
        manual_review: manualReview,
        target_duration: targetDuration
      });
      setSessionId(res.data.session_id);
      setProcessResponse(res.data);
    } catch (err) {
      setLogs(prev => [...prev, `[ERROR] Connection failed: ${err.message}`]);
      setStatus('ERROR');
    }
  };

  const [selectedVideo, setSelectedVideo] = useState(null);
  const [publishStatus, setPublishStatus] = useState({});
  const currentStepIndex = steps.findIndex(s => s.id === status);

  return (
    <div className={`min-h-screen transition-colors duration-500 overflow-x-hidden ${isDark ? 'dark bg-[#050505]' : 'bg-slate-50'}`}>
      
      {activeVncJobId && (
        <LiveViewer 
          jobId={activeVncJobId} 
          onClose={() => setActiveVncJobId(null)} 
        />
      )}

      <div className="fixed inset-0 pointer-events-none overflow-hidden opacity-30">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-yt-red/10 blur-[120px] rounded-full animate-pulse-slow"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-tk-cyan/10 blur-[120px] rounded-full animate-pulse-slow" style={{ animationDelay: '2s' }}></div>
      </div>

      <nav className="relative z-50 flex flex-wrap items-center justify-between gap-y-4 px-4 sm:px-8 py-4 sm:py-6 border-b border-white/5 backdrop-blur-xl transition-all duration-500">
        <div className="flex items-center gap-2 sm:gap-4 group cursor-pointer w-full sm:w-auto justify-between sm:justify-start">
          <div className="flex items-center gap-2 sm:gap-4">
            <div className="bg-[#FF0000] px-2.5 sm:px-4 py-1.5 sm:py-2 rounded-[10px] sm:rounded-[14px] flex items-center justify-center shadow-[0_0_30px_rgba(255,0,0,0.4)] group-hover:scale-105 transition-transform duration-300">
              <span className="text-white font-black italic text-lg sm:text-3xl tracking-tighter leading-none">You</span>
            </div>
            <div className="relative flex items-center">
              <span className={`${isDark ? 'text-white' : 'text-slate-900'} font-black text-xl sm:text-4xl tracking-tighter hover:animate-glitch inline-block`} style={{ textShadow: isDark ? '3px 0 #25F4EE, -3px 0 #FE2C55' : 'none' }}>
                Tik
              </span>
              <div className="ml-2 sm:ml-5 h-5 sm:h-8 w-px bg-slate-300 dark:bg-white/20" />
              <div className="flex flex-col ml-2 sm:ml-5">
                <span className="text-[7px] sm:text-[11px] font-black tracking-[0.2em] sm:tracking-[0.3em] text-slate-500 dark:text-slate-300 uppercase">Studio</span>
                <span className="text-[7px] sm:text-[11px] font-black tracking-[0.2em] sm:tracking-[0.3em] text-yt-red uppercase">V6.0</span>
              </div>
            </div>
          </div>
          
          {/* Mobile Right Buttons (Hidden on sm) */}
          <div className="flex sm:hidden items-center gap-1.5">
            <button onClick={handleResetSession} className="p-2 bg-red-500/10 hover:bg-red-500/20 text-red-500 hover:scale-105 rounded-full transition-all duration-300 active:scale-90 flex items-center justify-center border border-red-500/20 dark:border-red-500/30">
              <RotateCcw size={16} />
            </button>
            <button onClick={() => setIsDark(!isDark)} className="p-2 bg-slate-200 dark:bg-white/5 hover:bg-slate-300 dark:hover:bg-white/10 rounded-full text-slate-600 dark:text-slate-400 transition-all active:scale-90">
              {isDark ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <div className="relative">
              <button onClick={() => setShowSettings(!showSettings)} className={`p-2 bg-slate-200 dark:bg-white/5 hover:bg-slate-300 dark:hover:bg-white/10 rounded-full text-slate-600 dark:text-slate-400 transition-all ${showSettings ? 'bg-yt-red/10 text-yt-red' : ''}`}>
                <Settings size={16} />
              </button>
            </div>
          </div>
        </div>

        <div className="flex order-last sm:order-none w-full sm:w-auto justify-center bg-slate-200 dark:bg-white/5 p-1 rounded-xl border border-slate-300 dark:border-white/10 transition-colors">
          <button onClick={() => setActiveTab('studio')} className={`flex items-center justify-center flex-1 sm:flex-none gap-1.5 sm:gap-2 px-3 sm:px-6 py-2 rounded-lg transition-all text-sm ${activeTab === 'studio' ? 'bg-white dark:bg-white/10 text-slate-900 dark:text-white shadow-lg' : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'}`}>
            <Monitor size={16} /> <span className="font-medium sm:inline">Studio</span>
          </button>
          <button onClick={() => setActiveTab('results')} className={`flex items-center justify-center flex-1 sm:flex-none gap-1.5 sm:gap-2 px-3 sm:px-6 py-2 rounded-lg transition-all text-sm ${activeTab === 'results' ? 'bg-white dark:bg-white/10 text-slate-900 dark:text-white shadow-lg' : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'}`}>
            <Layout size={16} /> <span className="font-medium sm:inline">Gallery</span>
            {results.length > 0 && <span className="flex h-2 w-2 rounded-full bg-yt-red animate-pulse ml-1 sm:ml-2"></span>}
          </button>
        </div>

        <div className="hidden sm:flex items-center gap-4">
          <div className="hidden md:flex flex-col items-end">
            <div className="text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase tracking-widest">System Status</div>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></span>
              <span className="text-xs font-mono text-green-500">BACKEND_ONLINE</span>
            </div>
          </div>
          <div className="h-8 w-px bg-slate-200 dark:bg-white/10 mx-2" />
          <button 
            onClick={handleResetSession} 
            className="p-2.5 bg-red-500/10 hover:bg-red-500/20 text-red-500 hover:scale-105 rounded-full transition-all duration-300 active:scale-90 flex items-center justify-center border border-red-500/20 dark:border-red-500/30"
            title="Reset Session"
          >
            <RotateCcw size={20} />
          </button>
          <button onClick={() => setIsDark(!isDark)} className="p-2.5 bg-slate-200 dark:bg-white/5 hover:bg-slate-300 dark:hover:bg-white/10 rounded-full text-slate-600 dark:text-slate-400 transition-all active:scale-90">
            {isDark ? <Sun size={20} /> : <Moon size={20} />}
          </button>
          <div className="relative">
            <button onClick={() => setShowSettings(!showSettings)} className={`p-2.5 bg-slate-200 dark:bg-white/5 hover:bg-slate-300 dark:hover:bg-white/10 rounded-full text-slate-600 dark:text-slate-400 transition-all ${showSettings ? 'bg-yt-red/10 text-yt-red' : ''}`}>
              <Settings size={20} />
            </button>
            <AnimatePresence>
              {showSettings && (
                <motion.div initial={{ opacity: 0, y: 15, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 15, scale: 0.95 }} className="fixed sm:absolute right-2 sm:right-0 left-2 sm:left-auto top-16 sm:top-auto mt-2 sm:mt-6 w-auto sm:w-[420px] glass-card p-0 shadow-[0_40px_100px_rgba(0,0,0,0.5)] border-white/10 z-[100] overflow-visible max-h-[80vh] overflow-y-auto">
                  <div className="bg-gradient-to-r from-slate-50 to-white dark:from-[#151515] dark:to-[#1a1a1a] p-8 border-b border-slate-200 dark:border-white/5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-xl bg-yt-red/10 flex items-center justify-center text-yt-red shadow-inner"><Settings size={22} className="animate-spin-slow" /></div>
                        <div>
                          <h4 className="text-[13px] font-black uppercase tracking-[0.2em] text-slate-900 dark:text-white">Studio Preferences</h4>
                          <p className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mt-0.5">Configuration v6.0.4</p>
                        </div>
                      </div>
                      <button onClick={() => setShowSettings(false)} className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-slate-200 dark:hover:bg-white/10 text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors">
                        <div className="text-2xl rotate-45 font-light leading-none">+</div>
                      </button>
                    </div>
                  </div>
                  <div className="p-8 space-y-10 bg-white dark:bg-[#0a0a0a]/80">
                    <div className="space-y-10">
                      <PremiumSelect label="Transcription Engine" value={selectedModel} options={availableModels} onChange={setSelectedModel} icon={Cpu} color="text-purple-400" isActive={status === 'VOCAL_ANALYSIS'} />
                      <PremiumSelect label="Semantic AI (Google Brain)" value={selectedGoogleModel} options={googleModels} onChange={setSelectedGoogleModel} icon={Sparkles} color="text-yellow-400" isActive={status === 'SEMANTICS'} />
                      <PremiumSelect label="Visual Branding Style" value={selectedStyle} options={subtitleStyles.map(s => ({ id: s, name: `${s} Studio Preset`, desc: `High-retention ${s} layout & font` }))} onChange={setSelectedStyle} icon={Layout} color="text-pink-400" isActive={status === 'COMPOSITING'} />
                      <div className="h-px bg-slate-200 dark:bg-white/5 my-2" />
                      <PremiumSelect label="Vocal Engine (TTS)" value={selectedTTSEngine} options={ttsEngines} onChange={setSelectedTTSEngine} icon={Mic} color="text-emerald-400" isActive={status === 'TTS_SYNTHESIS'} />
                      {selectedTTSEngine !== 'original' && (
                        <PremiumSelect label="AI Vocal Persona" value={selectedTTSVoice} options={ttsVoices} onChange={setSelectedTTSVoice} icon={CheckCircle2} color="text-blue-400" isActive={status === 'TTS_SYNTHESIS'} />
                      )}
                    </div>
                  </div>
                  <div className="bg-slate-50 dark:bg-white/[0.02] px-8 py-5 flex justify-between items-center border-t border-slate-200 dark:border-white/5">
                    <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest">Utik Studio • Egyptian Edition</span>
                    <div className="flex gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-yt-red"></div>
                      <div className="w-1.5 h-1.5 rounded-full bg-tk-pink"></div>
                      <div className="w-1.5 h-1.5 rounded-full bg-tk-cyan"></div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </nav>

      <main className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
        <AnimatePresence mode="wait">
          {activeTab === 'studio' ? (
            <motion.div key="studio" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="space-y-12">
              <div className="text-center space-y-6 max-w-4xl mx-auto">
                {/* Hero Logo */}
                <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.1, type: 'spring', stiffness: 200 }} className="flex items-center justify-center gap-3 sm:gap-4 mx-auto">
                  <div className="bg-[#FF0000] px-5 sm:px-8 py-3 sm:py-4 rounded-[18px] sm:rounded-[22px] flex items-center justify-center shadow-[0_0_50px_rgba(255,0,0,0.5)] hover:scale-105 transition-transform duration-300">
                    <span className="text-white font-black italic text-4xl sm:text-6xl tracking-tighter leading-none">You</span>
                  </div>
                  <span className={`${isDark ? 'text-white' : 'text-slate-900'} font-black text-5xl sm:text-7xl tracking-tighter`} style={{ textShadow: isDark ? '4px 0 #25F4EE, -4px 0 #FE2C55' : 'none' }}>
                    Tik
                  </span>
                </motion.div>

                <motion.h1 initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="text-3xl sm:text-5xl md:text-7xl font-black tracking-tight leading-[0.95] text-slate-900 dark:text-white">
                  Turn Any Video into <br />
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-yt-red via-tk-pink to-tk-cyan">Viral Masterpieces</span>
                </motion.h1>
                <p className="text-slate-500 dark:text-slate-300 text-base sm:text-xl max-w-2xl mx-auto font-medium">
                  Professional Egyptian AI processing with cinematic rendering. Auto-segments, transcribes, and composites your content for maximum engagement.
                </p>
              </div>

              {/* Google Auth Card — Landing Page */}
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="max-w-3xl mx-auto">
                <div className={`relative overflow-hidden rounded-2xl border transition-all duration-500 ${
                  googleUser 
                    ? 'bg-gradient-to-r from-green-500/5 via-emerald-500/5 to-green-500/5 dark:from-green-500/10 dark:via-emerald-500/5 dark:to-green-500/10 border-green-500/20 dark:border-green-500/15' 
                    : 'bg-white/80 dark:bg-white/[0.03] border-slate-200 dark:border-white/10 hover:border-purple-500/30 dark:hover:border-purple-500/20'
                }`}>
                  <div className="px-5 py-3.5 flex items-center justify-between gap-4">
                    {googleUser ? (
                      <>
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="relative flex-shrink-0">
                            <img 
                              src={googleUser.picture} 
                              alt={googleUser.name} 
                              className="w-9 h-9 rounded-full border-2 border-green-500/30"
                              onError={(e) => { e.target.src = "https://lh3.googleusercontent.com/a/default-user=s96-c"; }}
                            />
                            <div className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-green-500 border-2 border-white dark:border-[#050505] flex items-center justify-center">
                              <Check size={8} className="text-white" />
                            </div>
                          </div>
                          <div className="min-w-0">
                            <div className="text-xs font-black text-slate-800 dark:text-white flex items-center gap-2">
                              <span className="truncate">{googleUser.name}</span>
                              <span className="text-[8px] bg-green-500/10 dark:bg-green-500/20 text-green-600 dark:text-green-400 font-extrabold px-1.5 py-0.5 rounded-md uppercase tracking-wider flex-shrink-0">Connected</span>
                            </div>
                            <div className="text-[10px] text-slate-400 dark:text-slate-500 truncate">{googleUser.email}</div>
                          </div>
                        </div>
                        <button 
                          onClick={handleGoogleSignOut}
                          className="text-[10px] font-black text-red-500 hover:bg-red-500/10 px-3 py-1.5 rounded-lg transition-colors active:scale-95 flex-shrink-0"
                        >
                          Sign Out
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={handleGoogleSignIn}
                        disabled={isGoogleSigningIn}
                        className="w-full flex items-center justify-center gap-3 py-1 transition-all duration-200 active:scale-[0.98] group/gauth"
                      >
                        {isGoogleSigningIn ? (
                          <Loader size={18} className="text-purple-500 animate-spin flex-shrink-0" />
                        ) : (
                          <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                          </svg>
                        )}
                        <span className="text-sm font-black text-slate-700 dark:text-slate-200 group-hover/gauth:text-slate-900 dark:group-hover/gauth:text-white transition-colors">
                          {isGoogleSigningIn ? (googleLoginDetail || 'Opening browser…') : 'Sign in with Google to Download & Publish'}
                        </span>
                      </button>
                    )}
                  </div>
                  {googleLoginDetail && !isGoogleSigningIn && (
                    <div className="px-5 pb-2.5">
                      <p className="text-[10px] text-center font-semibold text-red-500 dark:text-red-400 animate-pulse">{googleLoginDetail}</p>
                    </div>
                  )}


                </div>
              </motion.div>

              {/* YouTube Cookies Sync Input Card */}
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }} className="max-w-3xl mx-auto mt-4">
                <div className="relative overflow-hidden rounded-2xl border border-slate-200 dark:border-white/10 bg-white/80 dark:bg-white/[0.03] p-6 space-y-4 hover:border-purple-500/30 transition-all">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-purple-500/10 flex items-center justify-center text-purple-500 font-black">
                      ⚡
                    </div>
                    <div>
                      <h4 className="text-xs font-black uppercase tracking-[0.2em] text-slate-900 dark:text-white">🔑 YouTube Ingestion Cookies</h4>
                      <p className="text-[9px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mt-0.5">Bypass 403 Forbidden & Bot detection blocks on Railway</p>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <textarea
                      placeholder="Paste your exported YouTube cookies.txt or JSON data here to sync directly..."
                      className="w-full text-xs font-mono p-4 rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-black/40 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-purple-500 max-h-[120px] min-h-[80px] custom-scrollbar placeholder:text-slate-400 dark:placeholder:text-slate-600"
                      value={directPastedCookies}
                      onChange={(e) => setDirectPastedCookies(e.target.value)}
                    />
                    
                    <div className="flex items-center justify-between gap-4">
                      {directSyncResultMsg ? (
                        <span className={`text-xs font-bold leading-normal truncate ${
                          directSyncResultMsg.includes("🎉") ? "text-emerald-500" : "text-rose-500"
                        }`}>
                          {directSyncResultMsg}
                        </span>
                      ) : (
                        <span className="text-[10px] text-slate-400 dark:text-slate-500 font-medium">
                          JSON format is recommended (from EditThisCookie or similar extensions).
                        </span>
                      )}
                      
                      <button
                        type="button"
                        onClick={handleDirectCookiesSync}
                        disabled={!directPastedCookies.trim() || directSyncing}
                        className="text-center text-xs font-black text-white bg-gradient-to-r from-purple-500 to-pink-500 px-6 py-2.5 rounded-xl transition-all cursor-pointer shadow-md hover:shadow-purple-500/10 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none border-none uppercase tracking-wider shrink-0"
                      >
                        {directSyncing ? "Syncing..." : "Sync Cookies"}
                      </button>
                    </div>
                  </div>
                </div>
              </motion.div>

              <div className="max-w-3xl mx-auto relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-yt-red via-tk-pink to-tk-cyan rounded-2xl blur opacity-20 group-focus-within:opacity-40 transition-opacity duration-500"></div>
                <div className="relative glass-card p-4 flex flex-col gap-4">

                  <div className="flex bg-slate-100 dark:bg-white/5 p-1 rounded-xl mb-2 border border-slate-200 dark:border-white/5">
                    <button onClick={() => handleSwitchMode('clip')} className={`flex-1 flex justify-center items-center gap-2 py-2.5 rounded-lg text-sm font-black uppercase tracking-wider transition-all ${mode === 'clip' ? 'bg-white dark:bg-white/10 shadow-md text-yt-red' : 'text-slate-500 hover:text-slate-900 dark:hover:text-white'}`}>
                      <Scissors size={16} /> Clip Mode
                    </button>
                    <button onClick={() => handleSwitchMode('create')} className={`flex-1 flex justify-center items-center gap-2 py-2.5 rounded-lg text-sm font-black uppercase tracking-wider transition-all ${mode === 'create' ? 'bg-white dark:bg-white/10 shadow-md text-emerald-500' : 'text-slate-500 hover:text-slate-900 dark:hover:text-white'}`}>
                      <PenTool size={16} /> Create Mode
                    </button>
                  </div>

                  {status === 'WAITING_FOR_REVIEW' ? (
                    <ReviewPortal sessionId={sessionId} isDark={isDark} onCommit={() => setStatus('RESUMING')} />
                  ) : (
                    <>
                      {mode === 'clip' && (
                        <>
                          <div className="flex flex-col md:flex-row items-center gap-2">
                            <div className="flex-1 flex items-center gap-3 px-6 py-4 w-full bg-slate-100 dark:bg-white/5 rounded-xl border border-slate-200 dark:border-white/10 focus-within:border-yt-red transition-all">
                              <LinkIcon className="text-slate-400" size={20} />
                              <input type="text" placeholder="Paste YouTube, TikTok or Instagram URL..." className="bg-transparent border-none outline-none w-full text-[15px] text-slate-900 dark:text-white font-bold placeholder:text-slate-400" value={url} onChange={(e) => setUrl(e.target.value)} />
                            </div>
                            <div className="flex items-center gap-3 px-4 py-3 bg-slate-200/50 dark:bg-white/10 rounded-xl">
                              <div className="flex flex-col">
                                <span className="text-[10px] font-black uppercase tracking-tighter text-slate-500 dark:text-slate-400">Workflow</span>
                                <span className="text-xs font-bold text-slate-900 dark:text-white">Let Me Edit</span>
                              </div>
                              <button onClick={() => setManualReview(!manualReview)} className={`w-12 h-6 rounded-full transition-all relative ${manualReview ? 'bg-yt-red' : 'bg-slate-300 dark:bg-white/10'}`}>
                                <motion.div animate={{ x: manualReview ? 26 : 4 }} className="absolute top-1 left-0 w-4 h-4 rounded-full bg-white shadow-sm" />
                              </button>
                            </div>
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="flex items-center gap-3 px-6 py-3 bg-slate-100 dark:bg-white/5 rounded-xl border border-slate-200 dark:border-white/10 focus-within:border-yt-red/50 transition-all">
                              <Sparkles className="text-slate-400" size={16} />
                              <input type="text" placeholder="Song Name (Optional for Lyric Fix)" className="bg-transparent border-none outline-none w-full text-xs text-slate-900 dark:text-white font-bold" value={songName} onChange={(e) => setSongName(e.target.value)} />
                            </div>
                            <div className="flex items-center gap-3 px-6 py-3 bg-slate-100 dark:bg-white/5 rounded-xl border border-slate-200 dark:border-white/10 focus-within:border-yt-red/50 transition-all">
                              <Monitor className="text-slate-400" size={16} />
                              <input type="text" placeholder="Artist Name (Optional)" className="bg-transparent border-none outline-none w-full text-xs text-slate-900 dark:text-white font-bold" value={artistName} onChange={(e) => setArtistName(e.target.value)} />
                            </div>
                          </div>
                        </>
                      )}

                      {mode === 'create' && (
                        <div className="space-y-3">
                          <div className="flex-1 flex items-start gap-3 px-6 py-4 w-full bg-slate-100 dark:bg-white/5 rounded-xl border border-slate-200 dark:border-white/10 focus-within:border-emerald-500 transition-all">
                            <Sparkles className="text-emerald-500 mt-1" size={20} />
                            <textarea dir="auto" placeholder="Paste or type your lyrics here (Leave a blank line between stanzas)..." className="bg-transparent border-none outline-none w-full text-[15px] text-slate-900 dark:text-white font-bold resize-none h-40 placeholder:text-slate-400 custom-scrollbar" value={promptText} onChange={(e) => setPromptText(e.target.value)} />
                          </div>
                          <div className="bg-slate-100 dark:bg-white/5 rounded-xl border border-slate-200 dark:border-white/10 p-5">
                            <label className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 dark:text-slate-300 mb-3 flex items-center gap-2">
                              <Music size={14} className="text-tk-cyan" /> Master Track Mix (Optional)
                            </label>
                            <div className="flex flex-wrap gap-2">
                              {MUSIC_GENRES.map(genre => (
                                <button
                                  key={genre}
                                  onClick={() => toggleGenre(genre)}
                                  className={`px-3 py-1.5 rounded-lg text-[11px] font-black uppercase tracking-wider transition-all border shadow-sm active:scale-95 ${selectedGenres.includes(genre) ? 'bg-tk-cyan text-white border-tk-cyan' : 'bg-white dark:bg-black text-slate-500 dark:text-slate-300 border-slate-200 dark:border-white/10 hover:border-tk-cyan/50'}`}
                                >
                                  {genre}
                                </button>
                              ))}
                            </div>
                          </div>

                          <div className="bg-slate-100 dark:bg-white/5 rounded-xl border border-slate-200 dark:border-white/10 p-5">
                            <div className="flex items-center justify-between mb-3">
                              <label className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 dark:text-slate-300 flex items-center gap-2">
                                <Settings size={14} className="text-emerald-500" /> Target Duration
                              </label>
                              <span className="text-xs font-black text-emerald-500">{targetDuration}s</span>
                            </div>
                            <input 
                              type="range" 
                              min="5" 
                              max="60" 
                              step="5" 
                              value={targetDuration} 
                              onChange={(e) => setTargetDuration(parseInt(e.target.value))} 
                              className="w-full h-2 bg-slate-200 dark:bg-white/10 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-emerald-500 [&::-webkit-slider-thumb]:shadow-lg" 
                            />
                            <div className="flex justify-between mt-2 text-[9px] font-bold text-slate-400">
                              <span>5s</span>
                              <span>30s</span>
                              <span>60s</span>
                            </div>
                          </div>
                        </div>
                      )}

                      <button onClick={handleStart} disabled={status !== 'IDLE' && status !== 'COMPLETED' && status !== 'ERROR'} className={`btn-primary w-full flex justify-center gap-3 ${mode === 'create' ? 'bg-emerald-500 hover:bg-emerald-600 shadow-[0_0_20px_rgba(16,185,129,0.3)] border-none' : ''}`}>
                        <span className="text-lg uppercase tracking-wider text-white">
                          {status === 'IDLE' ? (mode === 'clip' ? 'Analyze & Slice' : 'Generate & Produce') : 'Processing...'}
                        </span>
                        <Play size={18} fill="currentColor" className="text-white" />
                      </button>
                    </>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8 pt-6 sm:pt-8">
                <div className="lg:col-span-2 space-y-6">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-black uppercase tracking-[0.2em] text-slate-500 dark:text-slate-300">Production Pipeline</h3>
                    <div className="text-[10px] font-mono px-3 py-1 bg-yt-red/10 rounded-full border border-yt-red/20 text-yt-red">{status} — {Math.round(progress)}%</div>
                  </div>

                  <div className="glass-card p-4 sm:p-10 space-y-8 sm:space-y-12 overflow-x-auto">
                    <div className="relative flex justify-between">
                      <div className="absolute top-6 left-0 w-full h-[1px] bg-white/5">
                        <motion.div className="h-full bg-gradient-to-r from-yt-red via-tk-pink to-tk-cyan" initial={{ width: 0 }} animate={{ width: `${progress}%` }} transition={{ duration: 1.5, ease: "circOut" }} />
                      </div>

                      {steps.map((step, idx) => {
                        const Icon = step.icon;
                        const isCompleted = idx < currentStepIndex || status === 'COMPLETED';
                        const isActive = idx === currentStepIndex;

                        return (
                          <div key={step.id} className="relative z-10 flex flex-col items-center gap-4">
                            <motion.div initial={false} animate={{ scale: isActive ? 1.25 : 1, borderColor: isActive ? 'rgba(255,0,0,1)' : isCompleted ? 'rgba(34,197,94,1)' : isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.1)', backgroundColor: isActive ? 'rgba(255,0,0,0.1)' : isCompleted ? 'rgba(34,197,94,0.1)' : isDark ? 'rgba(0,0,0,0.4)' : 'rgba(0,0,0,0.02)' }} className="w-14 h-14 rounded-2xl border flex items-center justify-center backdrop-blur-3xl shadow-xl transition-all duration-700">
                              {isCompleted ? <CheckCircle2 className="text-green-500" size={24} /> : <Icon className={isActive ? (isDark ? 'text-white' : 'text-yt-red') : 'text-slate-400'} size={24} />}
                              {isActive && <motion.div className="absolute -inset-2 rounded-2xl border border-yt-red/50" animate={{ scale: [1, 1.4, 1], opacity: [0.5, 0, 0.5] }} transition={{ repeat: Infinity, duration: 2 }} />}
                            </motion.div>
                            <div className="flex flex-col items-center gap-1">
                              <span className={`text-[8px] sm:text-[10px] font-black uppercase tracking-widest text-center ${isActive ? 'text-white' : 'text-slate-500 dark:text-slate-400'}`}>{step.title}</span>
                              {isActive && <span className="text-[8px] font-mono text-yt-red animate-pulse">RUNNING...</span>}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="flex items-center justify-between text-slate-500 dark:text-slate-300">
                      <div className="flex items-center gap-2">
                        <Cpu size={14} className="text-yt-red" />
                        <span className="text-[10px] font-black uppercase tracking-[0.2em]">Live Pipeline Status</span>
                      </div>
                      <span className="text-[14px] font-black text-yt-red">{Math.round(progress)}%</span>
                    </div>

                    <div className="glass-card p-6 space-y-5 border-slate-200 dark:border-white/10">
                      <div className="text-xs text-slate-400 font-mono mb-2">
                        <div className="truncate">Session: {sessionId || '—'} • Last status: {lastPoll?.status || status}</div>
                        <div className="truncate">Process response: {processResponse ? JSON.stringify(processResponse) : 'none'}</div>
                        <div className="truncate">Last poll: {lastPoll ? JSON.stringify(lastPoll) : 'none'}</div>
                      </div>
                      <div className="h-3 w-full bg-slate-200 dark:bg-white/5 rounded-full overflow-hidden relative shadow-inner">
                        <motion.div
                          className="absolute top-0 left-0 h-full bg-gradient-to-r from-yt-red via-tk-pink to-tk-cyan"
                          initial={{ width: 0 }}
                          animate={{ width: `${progress}%` }}
                          transition={{ duration: 0.5, ease: "easeOut" }}
                        />
                      </div>

                      <div className="flex items-center gap-3 bg-slate-50 dark:bg-white/5 px-4 py-3 rounded-xl border border-slate-200 dark:border-white/5">
                        <div className="w-2 h-2 rounded-full bg-yt-red animate-pulse shadow-[0_0_8px_rgba(255,0,0,0.6)] shrink-0"></div>
                        <span className="text-xs font-mono font-medium text-slate-700 dark:text-slate-300 truncate">
                          {logs.length > 0 ? logs[logs.length - 1] : "Awaiting production initialization..."}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="space-y-6">
                  <div className="glass-card p-8 space-y-8">
                    <h4 className="text-xs font-black uppercase tracking-[0.2em] text-slate-500 dark:text-slate-300">Production Engine</h4>
                    <div className="space-y-6">
                      <div className="space-y-1">
                        <label className="text-[10px] text-slate-400 uppercase font-bold tracking-widest">Transcription Model</label>
                        <p className="font-black text-slate-900 dark:text-white uppercase tracking-tighter">{availableModels.find(m => m.id === selectedModel)?.name || 'AUTO-SELECT'}</p>
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] text-slate-400 uppercase font-bold tracking-widest">Semantic AI</label>
                        <p className="font-black text-slate-900 dark:text-white uppercase tracking-tighter">{googleModels.find(m => m.id === selectedGoogleModel)?.name || 'AUTO-SELECT'}</p>
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] text-slate-400 uppercase font-bold tracking-widest">Output Preset</label>
                        <p className="font-black text-slate-900 dark:text-white italic">TikTok / Shorts (9:16)</p>
                      </div>
                      <div className="space-y-1">
                        <label className="text-[10px] text-slate-400 uppercase font-bold tracking-widest">Vocal Synthesis</label>
                        <p className="font-black text-slate-900 dark:text-white uppercase tracking-tighter text-glow-emerald">
                          {selectedTTSEngine === 'original' ? 'Source Audio' : `AI: ${selectedTTSVoice}`}
                        </p>
                      </div>
                    </div>
                    <div className="pt-8 border-t border-slate-200 dark:border-white/5 space-y-4">
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-slate-500 dark:text-slate-400">Isolated Clips</span>
                        <span className="font-black text-yt-red">{results.length}</span>
                      </div>
                      <div className="h-1.5 w-full bg-slate-200 dark:bg-white/5 rounded-full overflow-hidden">
                        <motion.div className="h-full bg-yt-red" initial={{ width: 0 }} animate={{ width: `${progress}%` }} />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          ) : (
            <motion.div key="results" initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.98 }} className="space-y-10">
              <div className="flex flex-col sm:flex-row items-start sm:items-end justify-between gap-4 border-b border-slate-200 dark:border-white/5 pb-6 sm:pb-8">
                <div className="space-y-2">
                  <h2 className="text-3xl sm:text-5xl font-black tracking-tight italic text-slate-900 dark:text-white">Production Gallery</h2>
                  <p className="text-slate-500 dark:text-slate-300 font-medium tracking-wide">High-fidelity assets ready for distribution.</p>
                </div>
                <button onClick={() => setActiveTab('studio')} className="group flex items-center gap-3 text-sm font-black uppercase tracking-[0.2em] text-slate-400 hover:text-yt-red transition-colors">
                  Return to Studio <ChevronRight size={20} className="group-hover:translate-x-2 transition-transform" />
                </button>
              </div>

              {results.length === 0 ? (
                <div className="glass-card py-32 flex flex-col items-center justify-center text-center space-y-8">
                  <div className="w-24 h-24 rounded-full bg-slate-100 dark:bg-white/5 flex items-center justify-center text-slate-400 border border-slate-200 dark:border-white/5"><Layout size={48} /></div>
                  <div className="space-y-2">
                    <h3 className="text-2xl font-black text-slate-900 dark:text-white">Archive Empty</h3>
                    <p className="text-slate-500 dark:text-slate-400 max-w-xs mx-auto">No clips have been generated in this session yet.</p>
                  </div>
                  <button onClick={() => setActiveTab('studio')} className="btn-primary text-xs uppercase tracking-widest px-10 text-white">Start Production</button>
                </div>
              ) : (
                <div className="grid grid-cols-1 xs:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4 sm:gap-5">
                  {results.map((clip, idx) => (
                    <motion.div key={idx} initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: idx * 0.05 }} className="group relative glass-card overflow-hidden bg-white/50 dark:bg-black/40 border-slate-200 dark:border-white/5 hover:border-yt-red/30 transition-all duration-500">
                      <div className="aspect-[9/16] relative overflow-hidden">
                        {clip.thumbnail_url ? (
                          <img src={`${API_BASE}${clip.thumbnail_url}`} alt={clip.filename} className="w-full h-full object-cover opacity-80 group-hover:opacity-100 group-hover:scale-110 transition-all duration-700" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-slate-200 dark:text-slate-900 bg-slate-100 dark:bg-black"><Play size={80} fill="currentColor" /></div>
                        )}
                        <div className="absolute inset-0 bg-gradient-to-t from-white/90 dark:from-[#050505] via-transparent to-transparent opacity-80"></div>
                        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 opacity-100 lg:opacity-0 lg:group-hover:opacity-100 transition-all duration-500 bg-black/20 lg:bg-black/40 backdrop-blur-none lg:backdrop-blur-sm pointer-events-none">
                          <button onClick={() => setSelectedVideo(clip)} className="w-12 h-12 sm:w-16 sm:h-16 bg-white/80 lg:bg-white text-black rounded-full flex items-center justify-center shadow-[0_0_30px_rgba(255,255,255,0.3)] hover:scale-110 transition-transform pointer-events-auto"><Play size={24} fill="currentColor" className="sm:w-7 sm:h-7" /></button>
                          <span className="hidden lg:block text-[10px] font-black uppercase tracking-widest text-white">Preview Asset</span>
                        </div>
                        <div className="absolute bottom-4 left-4 right-4 sm:bottom-6 sm:left-6 sm:right-6 flex justify-between items-end z-10 pointer-events-none">
                          <div className="space-y-1">
                            <div className="text-sm sm:text-lg font-black tracking-tight truncate max-w-[80px] sm:max-w-[140px] uppercase text-slate-900 dark:text-white pointer-events-auto">{clip.filename.split('_').pop()}</div>
                          </div>
                          <div className="flex items-center gap-1.5 sm:gap-2 transform lg:group-hover:translate-y-0 lg:translate-y-2 opacity-100 lg:opacity-0 group-hover:opacity-100 transition-all pointer-events-auto">
                            <PublishDropdown clip={clip} publishStatus={publishStatus} setPublishStatus={setPublishStatus} googleUser={googleUser} setGoogleUser={setGoogleUser} handleGoogleSignIn={handleGoogleSignIn} handleGoogleSignOut={handleGoogleSignOut} isGoogleSigningIn={isGoogleSigningIn} googleLoginDetail={googleLoginDetail} triggerExtensionSync={triggerExtensionSync} setActiveVncJobId={setActiveVncJobId} />
                            <a href={`${API_BASE}${clip.url}`} download className="w-10 h-10 sm:w-12 sm:h-12 bg-white text-black rounded-xl sm:rounded-2xl flex items-center justify-center shadow-xl hover:bg-yt-red hover:text-white transition-all"><Download className="w-4 h-4 sm:w-5 sm:h-5" /></a>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <AnimatePresence>
        {selectedVideo && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[200] flex items-center justify-center p-6 md:p-12 overflow-hidden">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setSelectedVideo(null)} className="absolute inset-0 bg-black/60 backdrop-blur-[40px] transition-all duration-700" />
            <motion.div initial={{ opacity: 0, scale: 0.8, y: 40 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.8, y: 40 }} className="relative h-[70vh] sm:h-[80vh] aspect-[9/16] bg-black rounded-[32px] sm:rounded-[48px] shadow-[0_0_150px_rgba(0,0,0,0.9)] border border-white/20 overflow-hidden ring-1 ring-white/10 flex flex-col mt-10 sm:mt-0">
              <div className="absolute top-0 left-0 right-0 p-4 sm:p-8 bg-gradient-to-b from-black/80 to-transparent flex items-center justify-between z-[210]">
                <div className="space-y-1">
                  <h3 className="text-xs sm:text-sm font-black text-white uppercase tracking-wider truncate max-w-[120px] sm:max-w-[200px]">{selectedVideo.filename}</h3>
                </div>
                <div className="flex items-center gap-2 sm:gap-3">
                  <a href={`${API_BASE}${selectedVideo.url}`} download className="bg-white text-black hover:bg-yt-red hover:text-white px-3 sm:px-5 py-1.5 sm:py-2 rounded-lg sm:rounded-xl text-[9px] sm:text-[10px] font-black uppercase tracking-widest transition-all flex items-center gap-1.5 sm:gap-2 shadow-xl"><Download size={14} /> <span className="hidden sm:inline">Save</span></a>
                  <button onClick={() => setSelectedVideo(null)} className="w-8 h-8 sm:w-10 sm:h-10 bg-white/10 hover:bg-white/20 text-white rounded-lg sm:rounded-xl flex items-center justify-center backdrop-blur-3xl border border-white/20 transition-all active:scale-90"><div className="text-xl rotate-45 font-light">+</div></button>
                </div>
              </div>
              <div className="flex-1 w-full h-full overflow-hidden">
                <video src={`${API_BASE}${selectedVideo.url}`} controls autoPlay className="w-full h-full object-cover" />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showSyncGuideModal && (
          <motion.div 
            initial={{ opacity: 0 }} 
            animate={{ opacity: 1 }} 
            exit={{ opacity: 0 }} 
            className="fixed inset-0 z-[250] flex items-center justify-center p-4 md:p-6 overflow-y-auto"
          >
            {/* Backdrop */}
            <motion.div 
              initial={{ opacity: 0 }} 
              animate={{ opacity: 1 }} 
              exit={{ opacity: 0 }} 
              onClick={() => setShowSyncGuideModal(false)} 
              className="absolute inset-0 bg-black/70 backdrop-blur-[15px] transition-all duration-300" 
            />

            {/* Modal Card */}
            <motion.div 
              initial={{ opacity: 0, scale: 0.95, y: 20 }} 
              animate={{ opacity: 1, scale: 1, y: 0 }} 
              exit={{ opacity: 0, scale: 0.95, y: 20 }} 
              className="relative w-full max-w-lg bg-white dark:bg-[#1a1a1c] rounded-3xl border border-slate-200 dark:border-white/10 p-6 md:p-8 shadow-[0_0_50px_rgba(168,85,247,0.15)] flex flex-col gap-6 max-h-[90vh] overflow-y-auto"
            >
              {/* Close Button */}
              <button 
                onClick={() => setShowSyncGuideModal(false)}
                className="absolute top-5 right-5 w-8 h-8 rounded-full bg-slate-100 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 flex items-center justify-center text-slate-500 dark:text-slate-300 transition-all cursor-pointer font-bold border-none"
              >
                ✕
              </button>

              {/* Title & Badge */}
              <div className="flex justify-between items-start gap-4 pr-6">
                <div className="flex flex-col gap-1">
                  <span className="text-[10px] font-black uppercase tracking-[0.2em] text-purple-500">Secure Ingestion Setup</span>
                  <h3 className="text-xl sm:text-2xl font-black tracking-tight text-slate-800 dark:text-white capitalize">⚡ {syncPlatform} Sync Guide</h3>
                </div>
                <div className={`px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-wider flex items-center gap-1.5 shrink-0 ${extensionActive ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20 animate-pulse'}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${extensionActive ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
                  {extensionActive ? 'Connected' : 'Not Detected'}
                </div>
              </div>

              {/* Steps Layout */}
              <div className="flex flex-col gap-5 text-slate-600 dark:text-slate-300">
                {/* Step 1 */}
                <div className="flex gap-4 items-start">
                  <div className="w-8 h-8 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center font-black flex-shrink-0 text-sm border border-purple-500/20">1</div>
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-black text-slate-800 dark:text-white mb-0.5 uppercase tracking-wide">📥 Download Sync Extension</h4>
                    <p className="text-xs text-slate-500 leading-relaxed font-medium">Click the button below to get the official sync package. Unzip the folder to a permanent, safe location on your computer.</p>
                    <div className="mt-2">
                      <a 
                        href={`${API_BASE}/api/extension/download`}
                        className="inline-flex items-center gap-2 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white font-black text-[11px] uppercase tracking-wider px-4 py-2.5 rounded-xl transition-all shadow-md active:scale-95 cursor-pointer decoration-none"
                      >
                        📥 Download Extension ZIP
                      </a>
                    </div>
                  </div>
                </div>

                {/* Step 2 */}
                <div className="flex gap-4 items-start">
                  <div className="w-8 h-8 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center font-black flex-shrink-0 text-sm border border-purple-500/20">2</div>
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-black text-slate-800 dark:text-white mb-0.5 uppercase tracking-wide">🧩 Load in Developer Mode</h4>
                    <p className="text-xs text-slate-500 leading-relaxed font-medium">
                      Open a new tab in Chrome/Edge, navigate to <span className="font-mono text-purple-500 select-all bg-purple-500/5 px-1.5 py-0.5 rounded">chrome://extensions</span>, toggle **Developer Mode** (top-right) to **ON**, click **"Load unpacked"** (top-left), and select the unzipped extension folder.
                    </p>
                  </div>
                </div>

                {/* Step 3 */}
                <div className="flex gap-4 items-start">
                  <div className="w-8 h-8 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center font-black flex-shrink-0 text-sm border border-purple-500/20">3</div>
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-black text-slate-800 dark:text-white mb-0.5 uppercase tracking-wide">📺 Open Logged-In {syncPlatform} Tab</h4>
                    <p className="text-xs text-slate-500 leading-relaxed font-medium">
                      Ensure you have an active browser tab open at <span className="font-semibold text-slate-800 dark:text-white capitalize">{syncPlatform}.com</span> where you are fully logged in. The extension will grab the secure authentication token directly from this tab.
                    </p>
                  </div>
                </div>

                {/* Step 4 */}
                <div className="flex gap-4 items-start">
                  <div className="w-8 h-8 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center font-black flex-shrink-0 text-sm border border-purple-500/20">4</div>
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-black text-slate-800 dark:text-white mb-0.5 uppercase tracking-wide">⚡ Trigger Sync</h4>
                    <p className="text-xs text-slate-500 leading-relaxed font-medium mb-3">
                      {extensionActive 
                        ? `Perfect! The extension is connected. Click the button below to fetch and securely sync your session cookies in 1-click!`
                        : `Once loaded, return here (the extension status above will switch to CONNECTED) to trigger the secure automatic sync.`
                      }
                    </p>
                    {extensionActive ? (
                      <button
                        onClick={() => {
                          triggerExtensionSync(syncPlatform);
                          setShowSyncGuideModal(false);
                        }}
                        disabled={syncingExtension}
                        className="w-full text-center text-xs font-black text-white bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 py-3 rounded-2xl transition-all cursor-pointer shadow-md hover:shadow-emerald-500/20 active:scale-[0.98] border-none uppercase tracking-wider animate-pulse flex items-center justify-center gap-2"
                      >
                        ⚡ Sync {syncPlatform} Session Now
                      </button>
                    ) : (
                      <button
                        disabled
                        className="w-full text-center text-xs font-black text-slate-400 bg-slate-100 dark:bg-white/5 py-3 rounded-2xl border-none uppercase tracking-wider cursor-not-allowed opacity-60 flex items-center justify-center gap-2"
                      >
                        ⌛ Waiting for Extension...
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Alternate/Fallback Paste & Upload option */}
              <div className="border-t border-slate-100 dark:border-white/5 pt-4 mt-2 flex flex-col gap-3">
                <span className="text-[9px] font-black text-slate-400 dark:text-slate-500 uppercase tracking-widest">⚡ One-Click Direct Paste (Fastest)</span>
                <p className="text-xs text-slate-500 leading-normal font-medium">
                  Export cookies on your YouTube tab (using extensions like <em>Get cookies.txt LOCALLY</em>), copy, and paste the raw content below:
                </p>
                <textarea
                  placeholder="Paste your copied cookies.txt or JSON cookie data here..."
                  className="w-full text-xs font-mono p-3 rounded-2xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-black/20 text-slate-800 dark:text-white focus:outline-none focus:ring-1 focus:ring-purple-500 max-h-[80px] min-h-[60px]"
                  value={pastedCookies}
                  onChange={(e) => setPastedCookies(e.target.value)}
                />
                <div className="flex gap-2">
                  <input 
                    type="file" 
                    id="cookie-file-upload-modal" 
                    accept=".json,.txt" 
                    className="hidden" 
                    onChange={(e) => {
                      handleCookieFileUpload(e);
                      setShowSyncGuideModal(false);
                    }} 
                  />
                  <button 
                    type="button"
                    onClick={() => document.getElementById("cookie-file-upload-modal").click()}
                    className="flex-1 text-center text-xs font-bold text-slate-600 dark:text-slate-300 hover:text-slate-800 dark:hover:text-white bg-slate-100 dark:bg-white/5 py-2.5 rounded-xl transition-all cursor-pointer border-none"
                  >
                    📁 Upload File
                  </button>
                  <button 
                    type="button"
                    onClick={handlePastedCookiesSync}
                    disabled={!pastedCookies.trim() || syncingExtension}
                    className="flex-[2] text-center text-xs font-black text-white bg-gradient-to-r from-purple-500 to-pink-500 py-2.5 rounded-xl transition-all cursor-pointer shadow-md hover:shadow-purple-500/10 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none border-none"
                  >
                    ⚡ Sync Pasted Cookies
                  </button>
                </div>
              </div>

            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <footer className={`relative z-10 mt-12 sm:mt-20 px-4 sm:px-12 py-12 sm:py-20 border-t transition-colors duration-500 ${isDark ? 'border-white/5 bg-black' : 'border-slate-200 bg-slate-100'}`}>
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-8 sm:gap-12 text-slate-500 dark:text-slate-400">
          <div className="col-span-2 space-y-6">
            <div className={`flex items-center gap-2 transition-all duration-500 ${isDark ? 'grayscale opacity-50' : ''}`}>
              <div className="bg-yt-red text-white px-3 py-1 rounded-lg font-black italic text-xl shadow-lg">You</div>
              <span className={`font-black text-2xl ${isDark ? 'text-white' : 'text-slate-900'}`}>Tik</span>
            </div>
            <p className="text-sm max-w-sm leading-relaxed font-medium text-slate-500 dark:text-slate-400">The world's first AI-powered video production suite optimized for Egyptian dialect and culture. Built for creators, by engineers.</p>
          </div>
          <div className="space-y-4">
            <h5 className="text-slate-900 dark:text-white font-black uppercase text-xs tracking-[0.2em]">Engine</h5>
            <ul className="text-sm space-y-3 font-medium">
              <li className="hover:text-yt-red cursor-pointer transition-colors">Documentation</li>
              <li className="hover:text-yt-red cursor-pointer transition-colors">API Reference</li>
            </ul>
          </div>
          <div className="space-y-4">
            <h5 className="text-slate-900 dark:text-white font-black uppercase text-xs tracking-[0.2em]">Community</h5>
            <ul className="text-sm space-y-3 font-medium">
              <li className="hover:text-yt-red cursor-pointer transition-colors">Discord</li>
              <li className="hover:text-yt-red cursor-pointer transition-colors">Twitter (X)</li>
            </ul>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;