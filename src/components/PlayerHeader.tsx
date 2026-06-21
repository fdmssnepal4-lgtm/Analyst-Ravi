import React from 'react';
import { Player, Video } from '../types';

interface PlayerHeaderProps {
  player: Player;
  videos: Video[];
  activeDepartment?: 'batting' | 'bowling';
}

export default function PlayerHeader({ player, videos, activeDepartment }: PlayerHeaderProps) {
  const initials = player.name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const totalClips = videos.length;
  const isBowler = player.role === 'Bowler' || (player.role === 'All-rounder' && activeDepartment === 'bowling');

  // bowling stats
  const dotBowlCount = videos.filter((v) => v.category === 'dot_bowl').length;
  const runsBowlCount = videos.filter((v) => v.category === 'runs_bowl').length;
  const boundaryBowlCount = videos.filter((v) => v.category === 'boundary_bowl').length;

  // batting stats
  const dotPaceCount = videos.filter((v) => v.category === 'dot_pace').length;
  const dotSpinCount = videos.filter((v) => v.category === 'dot_spin').length;
  const runsPaceCount = videos.filter((v) => v.category === 'runs_pace').length;
  const runsSpinCount = videos.filter((v) => v.category === 'runs_spin').length;
  const wicketsCount = videos.filter((v) => v.category === 'wicket').length;

  return (
    <div className="bg-[#12161f] border border-[#252d3d] p-5 rounded-xl relative overflow-hidden shrink-0 select-none mb-6">
      {/* Visual Watermarked initials */}
      <div 
        className="absolute -right-4 -bottom-8 opacity-10 font-bold text-[96px] md:text-[130px] font-display text-[#6b7593] select-none pointer-events-none uppercase tracking-tighter"
      >
        {initials}{player.jersey !== 'N/A' ? player.jersey : ''}
      </div>

      <div className="flex flex-col md:flex-row gap-6 md:items-center justify-between relative z-10">
        <div className="flex items-center gap-5">
          {/* Profile Initials Hexagon Layout */}
          <div className="w-16 h-16 md:w-20 md:h-20 rounded-lg bg-[#1a1f2e] border-2 border-[#252d3d] flex items-center justify-center font-display text-2xl md:text-3.5xl text-white font-medium shrink-0 shadow-lg shadow-black/30">
            {initials}
          </div>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl md:text-3.5xl font-display font-bold uppercase tracking-wide leading-none text-[#e8eaf0] italic">
                {player.name}
              </h1>
              {player.province && (
                <span className="px-2 py-0.5 bg-[#003893] text-[9px] font-bold rounded text-white uppercase font-sans tracking-wide">
                  {player.province}
                </span>
              )}
            </div>
            
            <div className="flex flex-wrap items-center gap-2 mt-2.5">
              <span className="text-[10px] border border-[#252d3d] px-2 py-1 rounded bg-[#0a0d12] text-[#6b7593] font-mono uppercase">
                {player.role}
              </span>
              <span className="text-[10px] border border-[#252d3d] px-2 py-1 rounded bg-[#0a0d12] text-[#6b7593] font-mono uppercase">
                {player.hand}
              </span>
              {player.jersey && player.jersey !== 'N/A' && (
                <span className="text-[10px] border border-[#c8102e4d] px-2 py-1 rounded bg-[#c8102e1a] text-[#fca5af] font-mono uppercase">
                  Squad #{player.jersey}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Quick Stats Grid */}
        <div className="flex flex-wrap gap-4 md:gap-6 border-t md:border-t-0 border-[#252d3d]/50 pt-4 md:pt-0 max-w-full select-none justify-start md:justify-end">
          <div className="text-left md:text-right">
            <p className="text-[9px] text-[#6b7593] uppercase font-mono tracking-wider">Footage</p>
            <p className="text-xl md:text-2xl font-bold font-mono">{totalClips}</p>
          </div>
          {isBowler ? (
            <>
              <div className="text-left md:text-right">
                <p className="text-[9px] text-[#6b7593] uppercase font-mono tracking-wider">Dot ball</p>
                <p className="text-xl md:text-2xl font-bold font-mono text-cyan-400">{dotBowlCount}</p>
              </div>
              <div className="text-left md:text-right">
                <p className="text-[9px] text-[#6b7593] uppercase font-mono tracking-wider">runs</p>
                <p className="text-xl md:text-2xl font-bold font-mono text-green-400">{runsBowlCount}</p>
              </div>
              <div className="text-left md:text-right">
                <p className="text-[9px] text-[#6b7593] uppercase font-mono tracking-wider">boundary's</p>
                <p className="text-xl md:text-2xl font-bold font-mono text-amber-500">{boundaryBowlCount}</p>
              </div>
            </>
          ) : (
            <>
              <div className="text-left md:text-right">
                <p className="text-[9px] text-[#6b7593] uppercase font-mono tracking-wider">Dot vs Pace</p>
                <p className="text-xl md:text-2xl font-bold font-mono text-violet-400">{dotPaceCount}</p>
              </div>
              <div className="text-left md:text-right">
                <p className="text-[9px] text-[#6b7593] uppercase font-mono tracking-wider">Dot vs Spin</p>
                <p className="text-xl md:text-2xl font-bold font-mono text-cyan-400">{dotSpinCount}</p>
              </div>
              <div className="text-left md:text-right">
                <p className="text-[9px] text-[#6b7593] uppercase font-mono tracking-wider">runs vs pace</p>
                <p className="text-xl md:text-2xl font-bold font-mono text-amber-500">{runsPaceCount}</p>
              </div>
              <div className="text-left md:text-right">
                <p className="text-[9px] text-[#6b7593] uppercase font-mono tracking-wider">runs vs spin</p>
                <p className="text-xl md:text-2xl font-bold font-mono text-green-400">{runsSpinCount}</p>
              </div>
              <div className="text-left md:text-right">
                <p className="text-[9px] text-[#6b7593] uppercase font-mono tracking-wider">Wicket</p>
                <p className="text-xl md:text-2xl font-bold font-mono text-red-500">{wicketsCount}</p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
