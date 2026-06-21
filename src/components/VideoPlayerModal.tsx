import React from 'react';
import { motion } from 'motion/react';
import { X, Calendar, User, Eye, Info } from 'lucide-react';
import { Video } from '../types';

interface VideoPlayerModalProps {
  isOpen: boolean;
  video: Video | null;
  onClose: () => void;
}

const CAT_COLORS = {
  strength: { label: 'Strength', emoji: '💪', border: 'border-green-500/20 text-green-400 bg-green-500/10' },
  weakness: { label: 'Weakness', emoji: '⚠️', border: 'border-red-500/20 text-red-400 bg-red-500/10' },
  boundary: { label: 'Boundary', emoji: '🎯', border: 'border-amber-500/20 text-amber-500 bg-amber-500/10' },
  pace: { label: 'vs Pace', emoji: '⚡', border: 'border-violet-500/20 text-violet-400 bg-violet-500/10' },
  spin: { label: 'vs Spin', emoji: '🌀', border: 'border-cyan-500/20 text-cyan-400 bg-cyan-500/10' },
  dot: { label: 'Dot Ball', emoji: '●', border: 'border-slate-500/20 text-slate-300 bg-slate-500/10' },
};

export default function VideoPlayerModal({ isOpen, video, onClose }: VideoPlayerModalProps) {
  if (!isOpen || !video) return null;

  // YT parser helper
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
  const autoplayEmbedUrl = id ? `https://www.youtube.com/embed/${id}?autoplay=1&rel=0&modestbranding=1` : '';
  const currentCat = CAT_COLORS[video.category] || { label: 'General', emoji: '🏏', border: 'border-slate-700 text-slate-300' };

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 bg-black/95 flex items-center justify-center p-4 z-100 backdrop-blur-xs transition-opacity duration-300"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 15 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 15 }}
        onClick={(e) => e.stopPropagation()}
        className="bg-[#12161f] border border-[#252d3d] rounded-xl max-w-4xl w-full overflow-hidden relative flex flex-col md:flex-row max-h-[90vh]"
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[#6b7593] hover:text-white bg-[#1a1f2e] border border-[#252d3d] w-8 h-8 rounded-md flex items-center justify-center transition-all hover:cursor-pointer z-50 hover:bg-[#c8102e]/10 hover:border-[#c8102e]/30"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Video stream panel */}
        <div className="flex-1 bg-black flex items-center justify-center relative aspect-video md:max-w-[60%]">
          {autoplayEmbedUrl ? (
            <iframe
              src={autoplayEmbedUrl}
              title={video.title}
              className="absolute inset-0 w-full h-full border-none"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            ></iframe>
          ) : (
            <div className="text-center p-6 bg-[#1a1f2e] text-[#6b7593]">
              <Info className="w-8 h-8 mx-auto mb-2 text-[#6b7593]" />
              <p className="text-xs">Corrupted YouTube Video URL</p>
            </div>
          )}
        </div>

        {/* Content detail sidebar */}
        <div className="w-full md:w-[40%] p-6 flex flex-col justify-between overflow-y-auto max-h-[45vh] md:max-h-full">
          <div>
            <div className="flex flex-wrap gap-1 mb-3 pr-8">
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-[9px] font-mono uppercase tracking-wider border ${currentCat.border}`}>
                <span>{currentCat.emoji}</span>
                <span>{currentCat.label}</span>
              </span>
              {video.phase && (
                <span className="inline-flex items-center px-2 py-1 rounded-sm text-[9px] font-mono uppercase tracking-wider border border-[#252d3d] text-[#6b7593] bg-[#1a1f2e]">
                  {video.phase.split('(')[0].trim()}
                </span>
              )}
            </div>

            <h3 className="text-lg font-title font-bold text-[#e8eaf0] tracking-wide leading-snug mb-3">
              {video.title}
            </h3>

            <div className="space-y-2 mb-6">
              {video.opposition && (
                <div className="flex items-center gap-2 text-xs text-[#a0aec0]">
                  <span className="text-[#6b7593] w-20 font-mono text-[9px] uppercase tracking-widest">Matchup:</span>
                  <span className="font-semibold text-white">vs {video.opposition}</span>
                </div>
              )}
              {video.date && (
                <div className="flex items-center gap-2 text-xs text-[#a0aec0]">
                  <span className="text-[#6b7593] w-20 font-mono text-[9px] uppercase tracking-widest">Logged:</span>
                  <span className="text-[#e8eaf0]">{video.date}</span>
                </div>
              )}
            </div>

            <div>
              <div className="text-[10px] font-mono uppercase tracking-widest text-[#6b7593] mb-2 flex items-center gap-1]">
                <Eye className="w-3 h-3 text-[#c8102e]" /> Coaching Insights
              </div>
              {video.notes ? (
                <div className="p-4 bg-[#1a1f2e] border-l-4 border-[#c8102e] rounded-r-lg text-xs text-[#b3bacf] leading-relaxed italic">
                  "{video.notes}"
                </div>
              ) : (
                <div className="p-4 bg-[#11141c] rounded-lg text-xs text-[#3d4560] leading-relaxed italic text-center">
                  No coach tactical feedback recorded for this clip. Keep cataloging notes inside the Add Video menu.
                </div>
              )}
            </div>
          </div>

          <div className="mt-8 pt-4 border-t border-[#252d3d] flex items-center justify-between text-[10px] font-mono text-[#3d4560]">
            <span>SYSTEM LOG: {video.id}</span>
            <span>DATE: {new Date(video.addedAt).toLocaleDateString()}</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
