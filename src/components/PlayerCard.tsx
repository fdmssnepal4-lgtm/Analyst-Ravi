import React from 'react';
import { Player } from '../types';

interface PlayerCardProps {
  player: Player;
  isActive: boolean;
  videoCount: number;
  onClick: () => void;
  key?: React.Key;
}

export default function PlayerCard({ player, isActive, videoCount, onClick }: PlayerCardProps) {
  const initials = player.name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <div
      onClick={onClick}
      className={`group flex items-center justify-between gap-3 p-3 border-l-4 transition-all hover:bg-[#1a1f2e] cursor-pointer ${
        isActive
          ? 'bg-[#1a1f2e] border-[#c8102e]'
          : 'border-transparent'
      }`}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div
          className={`w-9 h-9 rounded-md flex items-center justify-center font-bold text-xs transition-colors shrink-0 ${
            isActive
              ? 'bg-[#c8102e] text-white'
              : 'bg-[#252d3d] text-[#6b7593] group-hover:text-[#e8eaf0]'
          }`}
        >
          {initials}
        </div>
        <div className="min-w-0">
          <p
            className={`text-xs font-semibold truncate transition-colors ${
              isActive ? 'text-white' : 'text-[#a0aec0] group-hover:text-white'
            }`}
          >
            {player.name}
          </p>
          <p className="text-[10px] text-[#6b7593] mt-0.5 font-sans truncate">
            {player.role}
          </p>
        </div>
      </div>

      <span
        className={`text-[9px] font-mono px-1.5 py-0.5 rounded border transition-colors shrink-0 ${
          isActive
            ? 'bg-[#0a0d12] border-[#c8102e] text-white'
            : 'bg-[#0a0d12] border-[#252d3d] text-[#6b7593] group-hover:text-[#a0aec0]'
        }`}
      >
        {videoCount < 10 ? `0${videoCount}` : videoCount}
      </span>
    </div>
  );
}
