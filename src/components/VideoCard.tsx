import React from 'react';
import { Play, Trash2 } from 'lucide-react';
import { Video } from '../types';

interface VideoCardProps {
  video: Video;
  onPlay: (id: string) => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
  playerRole?: string;
  key?: React.Key;
}

const COMBINED_CATS: Record<string, { label: string; emoji: string; stripeClass: string; pillClass: string }> = {
  dot_pace: { label: 'Dot ball vs Pace', emoji: '⚡', stripeClass: 'bg-violet-500', pillClass: 'bg-violet-500/10 text-violet-400 border-violet-500/20' },
  dot_spin: { label: 'Dot Ball vs Spin', emoji: '🌀', stripeClass: 'bg-cyan-500', pillClass: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20' },
  runs_pace: { label: 'Runs Vs pace', emoji: '🏃', stripeClass: 'bg-amber-600', pillClass: 'bg-amber-500/10 text-amber-500 border-amber-500/20' },
  runs_spin: { label: 'runs vs spin', emoji: '🏏', stripeClass: 'bg-green-500', pillClass: 'bg-green-500/10 text-green-400 border-green-500/20' },
  wicket: { label: 'Wicket', emoji: '🎳', stripeClass: 'bg-[#ef4444]', pillClass: 'bg-rose-500/10 text-rose-400 border-rose-500/20' },

  dot_bowl: { label: 'Dot ball', emoji: '●', stripeClass: 'bg-slate-500', pillClass: 'bg-slate-500/10 text-slate-300 border-slate-500/20' },
  runs_bowl: { label: 'runs', emoji: '🏃', stripeClass: 'bg-green-600', pillClass: 'bg-green-500/10 text-green-400 border-green-500/20' },
  boundary_bowl: { label: "boundary's", emoji: '🎯', stripeClass: 'bg-amber-500', pillClass: 'bg-amber-500/10 text-[#f6ad55] border-amber-500/20' },

  strength: { label: 'Strength', emoji: '💪', stripeClass: 'bg-green-500', pillClass: 'bg-green-500/10 text-green-400 border-green-500/20' },
  weakness: { label: 'Weakness', emoji: '⚠️', stripeClass: 'bg-red-500', pillClass: 'bg-red-500/10 text-red-400 border-red-500/20' },
  boundary: { label: 'Boundary', emoji: '🎯', stripeClass: 'bg-amber-500', pillClass: 'bg-amber-500/10 text-amber-500 border-amber-500/20' },
  wkt: { label: 'Wicket', emoji: '🎳', stripeClass: 'bg-[#ef4444]', pillClass: 'bg-rose-500/10 text-rose-400 border-rose-500/20' },
  pace: { label: 'vs Pace', emoji: '⚡', stripeClass: 'bg-violet-500', pillClass: 'bg-[#c8102e1a] text-violet-400 border-violet-500/20' },
  spin: { label: 'vs Spin', emoji: '🌀', stripeClass: 'bg-cyan-500', pillClass: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20' },
  dot: { label: 'Dot Ball', emoji: '●', stripeClass: 'bg-slate-500', pillClass: 'bg-slate-500/10 text-slate-300 border-slate-500/20' },
};

export default function VideoCard({ video, onPlay, onDelete, playerRole }: VideoCardProps) {
  // Extract YT video ID
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

  const id = getYTId(video.url);
  const thumbUrl = id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : null;
  const currentCat = COMBINED_CATS[video.category] || { label: 'General', emoji: '📹', stripeClass: 'bg-slate-700', pillClass: 'bg-slate-800 text-slate-200' };

  return (
    <div
      onClick={() => onPlay(video.id)}
      className="bg-[#12161f] border border-[#252d3d] rounded-xl overflow-hidden transition-all duration-300 hover:-translate-y-1 hover:border-[#c8102e]/30 group hover:shadow-xl hover:shadow-black/40 flex flex-col justify-between"
    >
      <div>
        {/* Thumbnail Screen area */}
        <div className="aspect-video bg-[#0a0d12] relative overflow-hidden select-none hover:cursor-pointer">
          {thumbUrl ? (
            <img
              src={thumbUrl}
              alt={video.title}
              className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-102"
              loading="lazy"
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center gap-2 bg-[#1a1f2e] text-[#6b7593]">
              <Play className="w-8 h-8 opacity-40 text-[#6b7593]" />
              <span className="text-[10px] font-mono">No Video Thumbnail</span>
            </div>
          )}

          {/* Hover Play button trigger overlay */}
          <div className="absolute inset-0 bg-black/60 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onPlay(video.id);
              }}
              className="w-11 h-11 rounded-full bg-[#c8102e] hover:bg-[#a50d24] flex items-center justify-center text-white transition-all shadow-lg hover:scale-105 hover:cursor-pointer"
            >
              <Play className="w-5 h-5 fill-current ml-0.5" />
            </button>
          </div>
        </div>

        {/* Category Stripe accent indicator */}
        <div className={`h-1 w-full ${currentCat.stripeClass}`}></div>

        <div className="p-4">
          <h4 className="text-xs font-bold text-[#e8eaf0] line-clamp-2 leading-relaxed tracking-wide mb-3 min-h-[32px]">
            {video.title}
          </h4>

          {/* Tag Badges */}
          <div className="flex flex-wrap gap-1.5 mb-1.5 select-none text-[9px] uppercase tracking-wider font-semibold font-mono">
            {video.opposition && (
              <span className="px-2 py-0.5 rounded-sm bg-blue-500/10 text-blue-300 border border-blue-500/25">
                vs {video.opposition}
              </span>
            )}
            {video.phase && (
              <span className="px-2 py-0.5 rounded-sm bg-orange-400/10 text-orange-400 border border-orange-400/25">
                {video.phase.split('(')[0].trim()}
              </span>
            )}
            <span className={`px-2 py-0.5 rounded-sm border ${currentCat.pillClass} inline-flex items-center gap-0.5 shrink-0`}>
              <span>{currentCat.emoji}</span>
              <span>{currentCat.label}</span>
            </span>
          </div>

          {video.date && (
            <div className="text-[9px] font-mono text-[#3d4560] uppercase mt-2">
              Logged: {video.date}
            </div>
          )}
        </div>
      </div>

      <div className="px-4 pb-4 pt-2 border-t border-[#252d3d]/30 flex items-center gap-2">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onPlay(video.id);
          }}
          className="flex-1 bg-[#1a1f2e] border border-[#252d3d] text-xs py-1.5 rounded-lg text-[#a0aec0] hover:text-[#e8eaf0] hover:border-[#6b7593] transition-colors hover:cursor-pointer font-sans"
        >
          ▶ Play Clip
        </button>
        <button
          onClick={(e) => onDelete(video.id, e)}
          className="px-2.5 bg-[#1a1f2e] border border-red-950/30 text-xs py-1.5 rounded-lg text-[#6b7593] hover:text-red-400 hover:border-red-500/30 transition-all hover:cursor-pointer"
          title="Delete Clip Log"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
