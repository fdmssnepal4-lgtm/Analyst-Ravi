import React, { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { X, Video, Youtube, HelpCircle } from 'lucide-react';
import { Player, Video as VideoType } from '../types';

interface AddVideoModalProps {
  isOpen: boolean;
  onClose: () => void;
  players: Player[];
  activePlayerId: string | null;
  presetCategory: string | null;
  onVideoAdded: (video: VideoType) => void;
}

const GET_CATS_FOR_DEPT = (dept: 'batting' | 'bowling') => {
  if (dept === 'bowling') {
    return {
      dot_bowl: { label: 'Dot ball', emoji: '●', color: 'border-slate-500/50 text-slate-300 bg-slate-500/10' },
      runs_bowl: { label: 'runs', emoji: '🏃', color: 'border-green-500/50 text-green-400 bg-green-500/10' },
      boundary_bowl: { label: "boundary's", emoji: '🎯', color: 'border-amber-500/50 text-amber-500 bg-amber-500/10' },
    };
  } else {
    return {
      dot_pace: { label: 'Dot ball vs Pace', emoji: '⚡', color: 'border-violet-500/50 text-violet-400 bg-violet-500/10' },
      dot_spin: { label: 'Dot Ball vs Spin', emoji: '🌀', color: 'border-cyan-500/50 text-cyan-400 bg-cyan-500/10' },
      runs_pace: { label: 'Runs Vs pace', emoji: '🏃', color: 'border-amber-500/50 text-amber-500 bg-amber-500/10' },
      runs_spin: { label: 'runs vs spin', emoji: '🏏', color: 'border-green-500/50 text-green-400 bg-green-500/10' },
      wicket: { label: 'Wicket', emoji: '🎳', color: 'border-rose-400/50 text-rose-400 bg-rose-500/10' },
    };
  }
};

export default function AddVideoModal({
  isOpen,
  onClose,
  players,
  activePlayerId,
  presetCategory,
  onVideoAdded,
}: AddVideoModalProps) {
  const [playerId, setPlayerId] = useState('');
  const [category, setCategory] = useState<string | null>(null);
  const [department, setDepartment] = useState<'batting' | 'bowling'>('batting');
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [date, setDate] = useState('');
  const [opposition, setOpposition] = useState('');
  const [phase, setPhase] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Handle active player mapping
  useEffect(() => {
    if (activePlayerId) {
      setPlayerId(activePlayerId);
    } else if (players.length > 0) {
      setPlayerId(players[0].id);
    }
  }, [activePlayerId, players]);

  // Handle auto-department setup based on selected player role
  useEffect(() => {
    if (playerId) {
      const selected = players.find((p) => p.id === playerId);
      if (selected) {
        if (selected.role === 'Bowler') {
          setDepartment('bowling');
        } else {
          setDepartment('batting');
        }
      }
    }
  }, [playerId, players]);

  // Set category preset if supplied
  useEffect(() => {
    if (presetCategory) {
      setCategory(presetCategory);
      if (['dot_bowl', 'runs_bowl', 'boundary_bowl'].includes(presetCategory)) {
        setDepartment('bowling');
      } else {
        setDepartment('batting');
      }
    }
  }, [presetCategory]);

  const selectedPlayer = players.find((p) => p.id === playerId);
  const CATS = GET_CATS_FOR_DEPT(department);

  if (!isOpen) return null;

  // YT helpers
  const getYTId = (inputUrl: string) => {
    if (!inputUrl) return null;
    const cleanUrl = inputUrl.trim();
    if (/^[a-zA-Z0-9_-]{11}$/.test(cleanUrl)) return cleanUrl;
    const patterns = [
      /youtu\.be\/([a-zA-Z0-9_-]{11})/,
      /youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})/,
      /youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/,
      /youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})/,
      /youtube\.com\/v\/([a-zA-Z0-9_-]{11})/,
    ];
    for (const p of patterns) {
      const m = cleanUrl.match(p);
      if (m) return m[1];
    }
    return null;
  };

  const videoId = getYTId(url);
  const embedUrl = videoId ? `https://www.youtube.com/embed/${videoId}?rel=0&modestbranding=1` : null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!playerId) {
      setError('Please select a player to tag.');
      return;
    }
    if (!category) {
      setError('Please select an intelligence category.');
      return;
    }
    if (!url.trim()) {
      setError('Please insert a YouTube video URL.');
      return;
    }
    if (!videoId) {
      setError('Could not extract a valid 11-character YouTube video ID. Please review your link.');
      return;
    }
    if (!title.trim()) {
      setError('Please enter a short descriptive title for this clip.');
      return;
    }

    setLoading(true);

    const newVideo: Omit<VideoType, 'id'> = {
      playerId,
      category,
      department,
      url: url.trim(),
      title: title.trim(),
      date: date.trim() || 'Unspecified Match',
      opposition: opposition.trim() || 'N/A',
      phase: phase || '— General Play —',
      notes: notes.trim(),
      addedAt: Date.now(),
    };

    try {
      const response = await fetch('/api/videos', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(newVideo),
      });

      if (!response.ok) {
        throw new Error('Failed to record video file in the database.');
      }

      const savedVideo = await response.json();
      onVideoAdded(savedVideo);
      setUrl('');
      setTitle('');
      setDate('');
      setOpposition('');
      setPhase('');
      setNotes('');
      onClose();
    } catch (err: any) {
      setError(err.message || 'Server connection error.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-100 overflow-y-auto backdrop-blur-xs">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 15 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 15 }}
        className="bg-[#12161f] border border-[#252d3d] rounded-xl max-w-lg w-full p-6 relative overflow-y-auto max-h-[95vh]"
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[#6b7593] hover:text-white bg-[#1a1f2e] border border-[#252d3d] w-8 h-8 rounded-md flex items-center justify-center transition-colors hover:cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-[#c8102e]/10 flex items-center justify-center text-[#c8102e]">
            <Video className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-display uppercase tracking-widest text-[#e8eaf0]">Add Clip Details</h2>
            <p className="text-xs text-[#6b7593]">Tag tactical performance footage with active coaching notes</p>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-950/40 border border-red-800/40 rounded-lg text-xs text-red-200">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-widest text-[#6b7593] mb-1.5">
              Player
            </label>
            <select
              value={playerId}
              onChange={(e) => setPlayerId(e.target.value)}
              disabled={loading}
              className="w-full bg-[#1a1f2e] border border-[#252d3d] text-[#e8eaf0] px-3 py-2 rounded-lg text-sm outline-none focus:border-[#c8102e] hover:cursor-pointer transition-colors"
            >
              {players.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.role})
                </option>
              ))}
            </select>
          </div>

          {selectedPlayer?.role === 'All-rounder' && (
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-[#6b7593] mb-1.5">
                Department / Discipline For Clip
              </label>
              <div className="grid grid-cols-2 gap-2 bg-[#1a1f2e] border border-[#252d3d] p-1 rounded-lg">
                <button
                  type="button"
                  onClick={() => {
                    setDepartment('batting');
                    setCategory(null);
                  }}
                  className={`py-1.5 rounded text-xs font-semibold uppercase tracking-wider transition-all hover:cursor-pointer flex items-center justify-center gap-2 ${
                    department === 'batting'
                      ? 'bg-[#c8102e] text-white font-bold shadow-md'
                      : 'text-[#6b7593] hover:text-[#e8eaf0]'
                  }`}
                >
                  <span>🏏</span>
                  <span>Batting clip</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setDepartment('bowling');
                    setCategory(null);
                  }}
                  className={`py-1.5 rounded text-xs font-semibold uppercase tracking-wider transition-all hover:cursor-pointer flex items-center justify-center gap-2 ${
                    department === 'bowling'
                      ? 'bg-[#c8102e] text-white font-bold shadow-md'
                      : 'text-[#6b7593] hover:text-[#e8eaf0]'
                  }`}
                >
                  <span>🎳</span>
                  <span>Bowling clip</span>
                </button>
              </div>
            </div>
          )}

          <div>
            <label className="block text-[10px] font-mono uppercase tracking-widest text-[#6b7593] mb-1.5">
              Intelligence Category
            </label>
            <div className="grid grid-cols-3 gap-2">
              {Object.entries(CATS).map(([key, cat]) => {
                const isSelected = category === key;
                return (
                  <button
                    type="button"
                    key={key}
                    onClick={() => setCategory(key as any)}
                    className={`p-3 rounded-lg border text-center transition-all hover:cursor-pointer ${
                      isSelected
                        ? `${cat.color} border-current ring-1 ring-offset-0 ring-current`
                        : 'border-[#252d3d] text-[#6b7593] hover:text-[#e8eaf0] hover:border-[#6b7593] bg-[#1a1f2e]'
                    }`}
                  >
                    <span className="block text-xl mb-1">{cat.emoji}</span>
                    <span className="text-[11px] font-semibold tracking-wide font-sans">{cat.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-mono uppercase tracking-widest text-[#6b7593] mb-1.5">
              YouTube Video URL / ID
            </label>
            <div className="flex gap-2">
              <div className="bg-[#1a1f2e] text-[#6b7593] px-3 rounded-lg border border-[#252d3d] flex items-center">
                <Youtube className="w-4 h-4" />
              </div>
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                disabled={loading}
                className="w-full bg-[#1a1f2e] border border-[#252d3d] text-[#e8eaf0] px-3 py-2 rounded-lg text-sm outline-none focus:border-[#c8102e] transition-colors"
              />
            </div>
            <p className="text-[10px] text-[#6b7593] font-mono mt-1">
              Supports typical video links, YouTube Shorts, embed links, or raw 11-char IDs.
            </p>

            {embedUrl && (
              <div className="mt-3 aspect-video bg-[#0a0d12] border border-[#252d3d] rounded-lg overflow-hidden relative">
                <iframe
                  src={embedUrl}
                  title="YouTube Preview"
                  className="w-full h-full"
                  allowFullScreen
                ></iframe>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-[#6b7593] mb-1.5">
                Clip Title / Description
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Backfoot pull shot vs speed"
                disabled={loading}
                className="w-full bg-[#1a1f2e] border border-[#252d3d] text-[#e8eaf0] px-3 py-2 rounded-lg text-sm outline-none focus:border-[#c8102e] transition-colors"
              />
            </div>

            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-[#6b7593] mb-1.5">
                Date / Tournament
              </label>
              <input
                type="text"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                placeholder="e.g. Feb 2026 - T20 Qualifiers"
                disabled={loading}
                className="w-full bg-[#1a1f2e] border border-[#252d3d] text-[#e8eaf0] px-3 py-2 rounded-lg text-sm outline-none focus:border-[#c8102e] transition-colors"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-[#6b7593] mb-1.5">
                Opposition Nation
              </label>
              <input
                type="text"
                value={opposition}
                onChange={(e) => setOpposition(e.target.value)}
                placeholder="e.g. India, UAE, Malaysia"
                disabled={loading}
                className="w-full bg-[#1a1f2e] border border-[#252d3d] text-[#e8eaf0] px-3 py-2 rounded-lg text-sm outline-none focus:border-[#c8102e] transition-colors"
              />
            </div>

            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-[#6b7593] mb-1.5">
                Match Phase
              </label>
              <select
                value={phase}
                onChange={(e) => setPhase(e.target.value)}
                disabled={loading}
                className="w-full bg-[#1a1f2e] border border-[#252d3d] text-[#e8eaf0] px-3 py-2 rounded-lg text-sm outline-none focus:border-[#c8102e] hover:cursor-pointer transition-colors"
              >
                <option value="">— Select Phase —</option>
                <option value="Powerplay (1-6)">Powerplay (Overs 1-6)</option>
                <option value="Middle (7-15)">Middle (Overs 7-15)</option>
                <option value="Death (16-20)">Death (Overs 16-20)</option>
                <option value="Multi-phase">Squad Drills / Training</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-mono uppercase tracking-widest text-[#6b7593] mb-1.5">
              Coaching Observations & Technical Logs
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Record foot placement details, bat velocity, dismissal pattern or run-scoring zones..."
              disabled={loading}
              rows={3}
              className="w-full bg-[#1a1f2e] border border-[#252d3d] text-[#e8eaf0] px-3 py-2 rounded-lg text-sm outline-none focus:border-[#c8102e] transition-colors resize-y min-h-[70px]"
            ></textarea>
          </div>

          <div className="flex gap-3 justify-end pt-3">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 bg-transparent text-[#6b7593] border border-[#252d3d] rounded-lg text-xs font-semibold hover:text-[#e8eaf0] transition-colors hover:cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-[#c8102e] text-white rounded-lg text-xs font-semibold hover:bg-[#a50d24] transition-all hover:translate-y-[-1px] disabled:opacity-50 hover:cursor-pointer"
            >
              {loading ? 'Recording...' : 'Record Video'}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}
