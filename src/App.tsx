import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  UserPlus, 
  Video, 
  Info, 
  AlertTriangle, 
  Trash2, 
  Calendar, 
  Check, 
  UserSquare, 
  Sparkles,
  HelpCircle
} from 'lucide-react';
import { Player, Video as VideoType } from './types';
import PlayerCard from './components/PlayerCard';
import PlayerHeader from './components/PlayerHeader';
import VideoCard from './components/VideoCard';
import AddPlayerModal from './components/AddPlayerModal';
import AddVideoModal from './components/AddVideoModal';
import VideoPlayerModal from './components/VideoPlayerModal';

const DEFAULT_CATS = {
  strength: { label: 'Strengths', emoji: '💪', color: 'text-green-400 bg-green-500/10' },
  weakness: { label: 'Weaknesses', emoji: '⚠️', color: 'text-red-400 bg-red-500/10' },
  boundary: { label: 'Boundaries', emoji: '🎯', color: 'text-amber-500 bg-amber-500/10' },
  pace: { label: 'vs Pace', emoji: '⚡', color: 'text-violet-400 bg-violet-500/10' },
  spin: { label: 'vs Spin', emoji: '🌀', color: 'text-cyan-400 bg-cyan-500/10' },
  dot: { label: 'Dot Balls', emoji: '●', color: 'text-slate-300 bg-slate-500/10' },
};

export default function App() {
  const [players, setPlayers] = useState<Player[]>([]);
  const [videos, setVideos] = useState<VideoType[]>([]);
  const [activePlayerId, setActivePlayerId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [activeDepartment, setActiveDepartment] = useState<'batting' | 'bowling'>('batting');
  
  // Modals management state
  const [isAddPlayerOpen, setIsAddPlayerOpen] = useState(false);
  const [isAddVideoOpen, setIsAddVideoOpen] = useState(false);
  const [activeVideoForPlayback, setActiveVideoForPlayback] = useState<VideoType | null>(null);
  const [presetCategory, setPresetCategory] = useState<string | null>(null);

  // loading state
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Initial DB loading effect
  useEffect(() => {
    const synchronizeData = async () => {
      try {
        const response = await fetch('/api/db');
        if (!response.ok) {
          throw new Error('Database server returned error context.');
        }
        const data = await response.json();
        setPlayers(data.players || []);
        setVideos(data.videos || []);
        
        if (data.players && data.players.length > 0) {
          setActivePlayerId(data.players[0].id);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to synchronize with localized file state on the Express process.');
      } finally {
        setIsLoading(false);
      }
    };

    synchronizeData();
  }, []);

  // Sync active department and tab when player changes
  useEffect(() => {
    const selected = players.find((p) => p.id === activePlayerId);
    if (selected) {
      if (selected.role === 'Bowler') {
        setActiveDepartment('bowling');
      } else {
        setActiveDepartment('batting');
      }
      setActiveTab('overview');
    }
  }, [activePlayerId, players]);

  // Handlers for additions & deletions
  const onPlayerAdded = (newPlayer: Player) => {
    setPlayers((prev) => [...prev, newPlayer]);
    setActivePlayerId(newPlayer.id);
    setActiveTab('overview');
  };

  const onVideoAdded = (newVideo: VideoType) => {
    setVideos((prev) => [...prev, newVideo]);
    setActiveTab(newVideo.category);
  };

  const deleteVideo = async (videoId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Deregister and delete this coaching footage?')) return;
    try {
      const response = await fetch(`/api/videos/${videoId}`, { method: 'DELETE' });
      if (!response.ok) {
        throw new Error('Failed to delete this video record.');
      }
      setVideos((prev) => prev.filter((v) => v.id !== videoId));
    } catch (err: any) {
      alert(err.message || 'Failed to delete video.');
    }
  };

  const deletePlayer = async (playerId: string) => {
    if (!confirm('Warning: De-registering this player will delete all their tagged video clips from the national database. Proceed?')) return;
    try {
      const response = await fetch(`/api/players/${playerId}`, { method: 'DELETE' });
      if (!response.ok) {
        throw new Error('Failed to de-register this player.');
      }
      
      const updatedPlayers = players.filter((p) => p.id !== playerId);
      setPlayers(updatedPlayers);
      setVideos((prev) => prev.filter((v) => v.playerId !== playerId));

      if (updatedPlayers.length > 0) {
        setActivePlayerId(updatedPlayers[0].id);
      } else {
        setActivePlayerId(null);
      }
      setActiveTab('overview');
    } catch (err: any) {
      alert(err.message || 'Failed to de-register player.');
    }
  };

  const triggerAddVideoWithCategoryPreset = (category: string) => {
    setPresetCategory(category);
    setIsAddVideoOpen(true);
  };

  const triggerGeneralAddVideo = () => {
    setPresetCategory(null);
    setIsAddVideoOpen(true);
  };

  const selectedPlayer = players.find((p) => p.id === activePlayerId) || null;
  const selectedPlayerRole = selectedPlayer ? selectedPlayer.role : 'Batter';
  const currentDepartment = selectedPlayerRole === 'Bowler' ? 'bowling' : (selectedPlayerRole === 'All-rounder' ? activeDepartment : 'batting');

  const CATS = currentDepartment === 'bowling' ? {
    dot_bowl: { label: 'Dot ball', emoji: '●', color: 'text-slate-300 bg-slate-500/10' },
    runs_bowl: { label: 'runs', emoji: '🏃', color: 'text-green-400 bg-green-500/10' },
    boundary_bowl: { label: "boundary's", emoji: '🎯', color: 'text-amber-500 bg-amber-500/10' },
  } : {
    dot_pace: { label: 'Dot ball vs Pace', emoji: '⚡', color: 'text-violet-400 bg-violet-500/10' },
    dot_spin: { label: 'Dot Ball vs Spin', emoji: '🌀', color: 'text-cyan-400 bg-cyan-500/10' },
    runs_pace: { label: 'Runs Vs pace', emoji: '🏃', color: 'text-amber-500 bg-amber-500/10' },
    runs_spin: { label: 'runs vs spin', emoji: '🏏', color: 'text-green-400 bg-green-500/10' },
    wicket: { label: 'Wicket', emoji: '🎳', color: 'text-rose-400 bg-rose-500/10' },
  };

  const selectedPlayerVideos = videos.filter((v) => {
    if (v.playerId !== activePlayerId) return false;
    const videoDept = v.department || (v.category === 'wkt' ? 'bowling' : (selectedPlayerRole === 'Bowler' ? 'bowling' : 'batting'));
    return videoDept === currentDepartment;
  }).map(v => {
    let mappedCat = v.category;
    if (currentDepartment === 'bowling') {
      if (v.category === 'dot_bowl' || v.category === 'runs_bowl' || v.category === 'boundary_bowl') {
        // already correct
      } else if (v.category === 'dot' || v.category === 'strength' || v.category === 'wkt') {
        mappedCat = 'dot_bowl';
      } else if (v.category === 'boundary') {
        mappedCat = 'boundary_bowl';
      } else {
        mappedCat = 'runs_bowl';
      }
    } else {
      // batting
      if (v.category === 'dot_pace' || v.category === 'dot_spin' || v.category === 'runs_pace' || v.category === 'runs_spin' || v.category === 'wicket') {
        // already correct
      } else if (v.category === 'dot') {
        mappedCat = 'dot_pace';
      } else if (v.category === 'pace') {
        mappedCat = 'runs_pace';
      } else if (v.category === 'spin') {
        mappedCat = 'runs_spin';
      } else if (v.category === 'wkt') {
        mappedCat = 'wicket';
      } else if (v.category === 'strength' || v.category === 'boundary') {
        mappedCat = 'runs_pace';
      } else {
        mappedCat = 'wicket';
      }
    }
    return { ...v, category: mappedCat };
  });

  // Quick stats computed
  const totalClipsInDatabase = videos.length;
  const lastLoggedClip = videos[videos.length - 1] || null;
  const lastLoggedPlayerName = lastLoggedClip 
    ? players.find((p) => p.id === lastLoggedClip.playerId)?.name || '—' 
    : '—';

  return (
    <div className="min-h-screen bg-[#0a0d12] flex flex-col font-sans select-none antialiased">
      {/* TOP HEADER STATUS BAR */}
      <header className="h-[56px] bg-[#12161f] border-b border-[#252d3d] flex items-center justify-between px-6 shrink-0 sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-[#c8102e] shadow-[0_0_10px_rgba(200,16,46,0.4)]"></div>
          <div>
            <h1 className="text-sm md:text-lg font-bold tracking-[0.1em] uppercase leading-none font-title">Nepal Women Cricket</h1>
            <p className="text-[9px] text-[#6b7593] tracking-[0.3em] uppercase mt-1 leading-none">Video Intelligence Hub • v2.4</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Gemini Pulse indicator */}
          <div className="hidden sm:inline-flex items-center gap-2 bg-[#c8102e1a] border border-[#c8102e4d] px-3 py-1 rounded-full select-none">
            <span className="w-1.5 h-1.5 rounded-full bg-[#c8102e] animate-pulse" />
            <span className="text-[10px] font-mono text-[#fca5af] tracking-wider uppercase">Gemini Intelligence Active</span>
          </div>

          <button
            onClick={() => setIsAddPlayerOpen(true)}
            className="px-3.5 py-2 border border-[#252d3d] text-[#a0aec0] hover:text-white rounded-lg text-xs font-semibold hover:border-white/20 transition-all active:scale-98 hover:cursor-pointer flex items-center gap-1.5 font-sans"
          >
            <UserSquare className="w-3.5 h-3.5" /> + Roster
          </button>
          
          <button
            onClick={triggerGeneralAddVideo}
            className="px-3.5 py-2 bg-[#c8102e] text-white rounded-lg text-xs font-semibold hover:bg-[#a50d24] transition-all hover:translate-y-[-1px] select-none shadow-md shadow-[#c8102e]/10 active:scale-98 hover:cursor-pointer flex items-center gap-1.5 font-sans"
          >
            <Video className="w-3.5 h-3.5" /> + Clip
          </button>
        </div>
      </header>

      {/* CORE WORKSPACE PANEL LAYOUT */}
      <div className="flex-1 flex flex-col md:flex-row min-h-0 [height:calc(100vh-56px)]">
        {/* SIDE SQUAD ROSTER PANEL CONTAINER */}
        <aside className="w-full md:w-[240px] bg-[#12161f] border-r border-[#252d3d] flex flex-col justify-between shrink-0 h-auto md:h-full overflow-y-auto">
          <div>
            <div className="p-4 border-b border-[#252d3d] bg-[#12161f] sticky top-0 z-20 flex items-center justify-between">
              <span className="text-[10px] font-mono uppercase tracking-widest text-[#6b7593]">
                Squad Roster
              </span>
              <span className="text-[10px] font-mono text-[#c8102e] bg-[#c8102e]/5 px-2 py-0.5 rounded-sm border border-[#c8102e]/10 font-bold">
                {players.length} Active
              </span>
            </div>

            {/* ROSTER LISTING */}
            <div className="divide-y divide-[#252d3d]/30 max-h-[300px] md:max-h-none overflow-y-auto custom-scrollbar">
              {players.length > 0 ? (
                players.map((p) => {
                  const playerVidsCount = videos.filter((v) => v.playerId === p.id).length;
                  return (
                    <PlayerCard
                      key={p.id}
                      player={p}
                      isActive={activePlayerId === p.id}
                      videoCount={playerVidsCount}
                      onClick={() => {
                        setActivePlayerId(p.id);
                        setActiveTab('overview');
                      }}
                    />
                  );
                })
              ) : (
                <div className="p-8 text-center text-xs text-[#3d4560] italic">
                  No registered players. Click Roster to begin setup.
                </div>
              )}
            </div>

            <button
              onClick={() => setIsAddPlayerOpen(true)}
              className="w-[calc(100%-32px)] mx-4 my-4 border border-dashed border-[#252d3d] hover:border-[#c8102e] text-xs text-[#6b7593] hover:text-[#c8102e] hover:bg-[#c8102e]/5 py-2.5 rounded-lg flex items-center justify-center gap-1.5 transition-all text-center hover:cursor-pointer select-none font-sans"
            >
              <UserPlus className="w-3.5 h-3.5" /> + Registered Player
            </button>
          </div>

          {/* SIDE PANEL INFRASTRUCTURE LABELS */}
          <div className="p-4 bg-[#0a0d12] border-t border-[#252d3d] select-none hidden md:block">
            <span className="text-[9px] font-mono uppercase tracking-widest text-[#6b7593] block mb-3 leading-none">
              High-Performance Telemetry
            </span>
            <div className="space-y-2 text-[10px] font-mono text-[#6b7593] mb-4">
              <div className="flex justify-between">
                <span>TOTAL CLIPS:</span>
                <span className="text-[#a0aec0] font-semibold">{totalClipsInDatabase}</span>
              </div>
              <div className="flex justify-between">
                <span>SQUAD SIZE:</span>
                <span className="text-[#a0aec0] font-semibold">{players.length}</span>
              </div>
            </div>

            <div className="flex justify-between text-[10px] font-mono text-[#6b7593] mb-2">
              <span>DATABASE LOAD</span>
              <span className="text-white font-bold">{Math.min(100, Math.max(12, players.length * 12 + totalClipsInDatabase * 4))}%</span>
            </div>
            <div className="w-full h-1 bg-[#12161f] rounded-full overflow-hidden">
              <div 
                className="h-full bg-[#003893] transition-all duration-500" 
                style={{ width: `${Math.min(100, Math.max(12, players.length * 12 + totalClipsInDatabase * 4))}%` }}
              ></div>
            </div>
          </div>
        </aside>

        {/* MIDDLE ANALYTICS VIEW */}
        <main className="flex-1 bg-[#0a0d12] flex flex-col min-w-0 h-full overflow-y-auto">
          {isLoading ? (
            <div className="flex-1 flex flex-col items-center justify-center space-y-3">
              <div className="relative w-8 h-8">
                <span className="absolute inset-0 rounded-full border-4 border-slate-800 border-t-[#c8102e] animate-spin"></span>
              </div>
              <span className="text-xs text-[#6b7593] font-mono uppercase tracking-widest animate-pulse">
                Synchronizing hub intelligence
              </span>
            </div>
          ) : error ? (
            <div className="flex-1 p-8 flex flex-col items-center justify-center text-center">
              <AlertTriangle className="w-10 h-10 text-red-500 mb-3" />
              <h2 className="text-[#e8eaf0] text-sm uppercase tracking-widest font-mono font-bold mb-2">
                Sync Failure
              </h2>
              <p className="text-xs text-[#6b7593] max-w-sm mb-4 leading-relaxed">
                {error}
              </p>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-[#e8eaf0] text-xs font-semibold rounded-lg font-mono tracking-wider hover:cursor-pointer"
              >
                Retry Stream Connect
              </button>
            </div>
          ) : !selectedPlayer ? (
            <div className="flex-1 flex flex-col items-center justify-center p-8 select-none text-center">
              <div className="text-4xl animate-bounce mb-3">🏏</div>
              <h2 className="font-display text-xl tracking-widest text-[#6b7593] uppercase font-semibold">
                No active player selected
              </h2>
              <p className="text-xs text-[#3d4560] max-w-xs mt-1 leading-relaxed">
                Choose from the registered national squad team roster in the left sidebar to analyze intelligence archives.
              </p>
              <button
                onClick={() => setIsAddPlayerOpen(true)}
                className="mt-4 px-4 py-2 bg-[#c8102e] text-white text-xs font-semibold rounded-lg hover:cursor-pointer hover:bg-[#a50d24]"
              >
                + Register First Player
              </button>
            </div>
          ) : (
            <div className="flex-1 flex flex-col h-full min-h-0 min-w-0">
              {/* Detailed Head Profile Bar */}
              <PlayerHeader player={selectedPlayer} videos={selectedPlayerVideos} activeDepartment={activeDepartment} />

              {/* Dynamic Discipline Selector for Dual-Discipline (All-rounders) */}
              {selectedPlayer.role === 'All-rounder' && (
                <div className="px-6 pb-5 flex">
                  <div className="bg-[#12161f] border border-[#252d3d] p-1 rounded-xl flex items-center gap-1 shadow-inner shadow-black/30">
                    <button
                      onClick={() => {
                        setActiveDepartment('batting');
                        setActiveTab('overview');
                      }}
                      className={`px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all duration-200 flex items-center gap-2 hover:cursor-pointer ${
                        activeDepartment === 'batting'
                          ? 'bg-[#c8102e] text-white shadow-md'
                          : 'text-[#6b7593] hover:text-white hover:bg-slate-800/40'
                      }`}
                    >
                      <span>🏏</span>
                      <span>Batting Discipline</span>
                    </button>
                    <button
                      onClick={() => {
                        setActiveDepartment('bowling');
                        setActiveTab('overview');
                      }}
                      className={`px-4 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all duration-200 flex items-center gap-2 hover:cursor-pointer ${
                        activeDepartment === 'bowling'
                          ? 'bg-[#c8102e] text-white shadow-md'
                          : 'text-[#6b7593] hover:text-white hover:bg-slate-800/40'
                      }`}
                    >
                      <span>🎳</span>
                      <span>Bowling Discipline</span>
                    </button>
                  </div>
                </div>
              )}

              {/* TABS BAR ACCENT SELECTOR */}
              <div className="border-b border-[#252d3d] bg-[#12161f] px-6 flex items-center justify-between shrink-0 overflow-x-auto select-none gap-4">
                <nav className="flex gap-1.5 md:gap-3 overflow-x-auto select-none no-scrollbar py-2">
                  <button
                    onClick={() => setActiveTab('overview')}
                    className={`px-3 py-2 text-xs font-semibold border-b-2 hover:cursor-pointer transition-all shrink-0 uppercase tracking-widest flex items-center gap-1.5 ${
                      activeTab === 'overview'
                        ? 'text-white border-[#c8102e] font-bold'
                        : 'text-[#6b7593] border-transparent hover:text-white'
                    }`}
                  >
                    📊 Overview
                  </button>
                  {Object.entries(CATS).map(([key, cat]) => {
                    const tagCount = selectedPlayerVideos.filter((v) => v.category === key).length;
                    const isActive = activeTab === key;
                    return (
                      <button
                        key={key}
                        onClick={() => setActiveTab(key)}
                        className={`px-3 py-2 text-xs font-semibold border-b-2 hover:cursor-pointer transition-all shrink-0 uppercase tracking-widest flex items-center gap-1.5 ${
                          isActive
                            ? 'text-white border-[#c8102e] font-bold'
                            : 'text-[#6b7593] border-transparent hover:text-white'
                        }`}
                      >
                        <span>{cat.emoji}</span>
                        <span>{cat.label}</span>
                        <span
                          className={`text-[9px] font-mono px-1.5 py-0.5 rounded-full border transition-colors ${
                            isActive
                              ? 'bg-[#c8102e] border-[#c8102e] text-white'
                              : 'bg-[#1a1f2e] border-[#252d3d] text-[#6b7593]'
                          }`}
                        >
                          {tagCount}
                        </span>
                      </button>
                    );
                  })}
                </nav>

                <button
                  onClick={() => deletePlayer(selectedPlayer.id)}
                  className="px-3 py-1 bg-[#1a1f2e] border border-red-950/20 text-[10px] uppercase font-mono tracking-wider text-[#6b7593] hover:text-red-500 hover:border-red-500/30 rounded-md shrink-0 transition-colors hover:cursor-pointer"
                >
                  De-register player
                </button>
              </div>

              {/* ACTIVE TAB DISPLAY VIEW */}
              <div className="flex-1 p-6 md:p-8 overflow-y-auto">
                {activeTab === 'overview' ? (
                  <div className="space-y-6 max-w-6xl mx-auto">
                    {/* Visual bento grid aggregating counts */}
                    <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
                      {Object.entries(CATS).map(([key, cat]) => {
                        const count = selectedPlayerVideos.filter((v) => v.category === key).length;
                        return (
                          <div
                            key={key}
                            onClick={() => setActiveTab(key)}
                            className="bg-[#12161f] border border-[#252d3d] p-4 rounded-xl flex items-center gap-4 hover:border-[#c8102e]/40 hover:cursor-pointer group transition-all"
                          >
                            <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center text-xl shrink-0 group-hover:scale-105 transition-transform">
                              {cat.emoji}
                            </div>
                            <div className="min-w-0">
                              <div className="text-xl font-mono font-bold text-white leading-none">
                                {count}
                              </div>
                              <div className="text-[10px] text-[#6b7593] mt-1 uppercase font-semibold tracking-wider font-sans whitespace-nowrap overflow-hidden text-overflow-ellipsis">
                                {cat.label}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Recent 3 uploads logs */}
                    <div>
                      <div className="flex items-center justify-between mb-4 mt-8 pr-1">
                        <h3 className="text-xs font-mono uppercase tracking-widest text-[#6b7593]">
                          Recently Logged Clips
                        </h3>
                        {selectedPlayerVideos.length > 3 && (
                          <span className="text-[10px] text-[#3d4560] italic">
                            All categories are filterable inside the top tabs bar
                          </span>
                        )}
                      </div>

                      {selectedPlayerVideos.length > 0 ? (
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                          {[...selectedPlayerVideos]
                            .reverse()
                            .slice(0, 3)
                            .map((v) => (
                              <VideoCard
                                key={v.id}
                                video={v}
                                playerRole={selectedPlayer.role}
                                onPlay={() => setActiveVideoForPlayback(v)}
                                onDelete={deleteVideo}
                              />
                            ))}
                        </div>
                      ) : (
                        <div className="text-center py-12 border border-dashed border-[#252d3d] bg-[#12161f]/30 rounded-xl relative overflow-hidden select-none">
                          <span className="block text-3xl mb-2">📹</span>
                          <p className="text-xs text-[#a0aec0] font-sans font-medium">No recorded tactical logs found for {selectedPlayer.name}.</p>
                          <p className="text-[10px] text-[#6b7593] max-w-xs mx-auto mt-1 leading-relaxed">
                            Click "+ Add Clip" or use any specific tab trigger to record their video drills.
                          </p>
                          <button
                            onClick={triggerGeneralAddVideo}
                            className="mt-4 px-4 py-2 bg-transparent border border-[#252d3d] hover:border-white/20 text-[#a0aec0] hover:text-white rounded-lg text-[10px] uppercase font-bold tracking-wider hover:cursor-pointer"
                          >
                            + Add First Clip
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="max-w-6xl mx-auto">
                    {/* Category specific tab view listing */}
                    <div className="flex items-center justify-between mb-6 pr-1 select-none">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-[#c8102e]" />
                        <h2 className="font-display text-lg md:text-xl font-bold tracking-widest text-white uppercase">
                          {(CATS as any)[activeTab]?.label} Insights
                        </h2>
                      </div>
                      
                      <button
                        onClick={() => triggerAddVideoWithCategoryPreset(activeTab as any)}
                        className="px-3.5 py-1.5 bg-[#c8102e]/10 border border-[#c8102e]/35 text-white rounded-lg text-xs font-semibold hover:bg-[#c8102e]/20 transition-all hover:translate-y-[-0.5px] shadow-sm active:scale-98 hover:cursor-pointer flex items-center gap-1.5 font-sans uppercase tracking-wider"
                      >
                        + Add {(CATS as any)[activeTab]?.label.slice(0, -1) || 'Clip'} Video
                      </button>
                    </div>

                    {selectedPlayerVideos.filter((v) => v.category === activeTab).length > 0 ? (
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                        {selectedPlayerVideos
                          .filter((v) => v.category === activeTab)
                          .map((v) => (
                            <VideoCard
                              key={v.id}
                              video={v}
                              playerRole={selectedPlayer.role}
                              onPlay={() => setActiveVideoForPlayback(v)}
                              onDelete={deleteVideo}
                            />
                          ))}
                      </div>
                    ) : (
                      <div className="text-center py-16 border border-dashed border-[#252d3d] bg-[#12161f]/40 rounded-xl max-w-md mx-auto relative overflow-hidden select-none">
                        <span className="block text-4xl mb-3">{(CATS as any)[activeTab]?.emoji}</span>
                        <p className="text-xs text-[#a0aec0] font-sans font-medium">No {(CATS as any)[activeTab]?.label.toLowerCase()} videos logged.</p>
                        <p className="text-[10px] text-[#6b7593] max-w-xs mx-auto mt-1 leading-relaxed px-4">
                          Keep building their high-performance profile. Tap the button above to tag their first segment in this tab.
                        </p>
                        <button
                          onClick={() => triggerAddVideoWithCategoryPreset(activeTab as any)}
                          className="mt-4 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-[#e8eaf0] text-xs font-semibold rounded-lg hover:cursor-pointer transition-colors"
                        >
                          + Log Clip Now
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </main>
      </div>

      {/* CORE MODALS PORTALS SCREEN OVERLAYS */}
      <AddPlayerModal
        isOpen={isAddPlayerOpen}
        onClose={() => setIsAddPlayerOpen(false)}
        onPlayerAdded={onPlayerAdded}
      />

      <AddVideoModal
        isOpen={isAddVideoOpen}
        onClose={() => setIsAddVideoOpen(false)}
        players={players}
        activePlayerId={activePlayerId}
        presetCategory={presetCategory}
        onVideoAdded={onVideoAdded}
      />

      <VideoPlayerModal
        isOpen={activeVideoForPlayback !== null}
        video={activeVideoForPlayback}
        onClose={() => setActiveVideoForPlayback(null)}
      />
    </div>
  );
}
