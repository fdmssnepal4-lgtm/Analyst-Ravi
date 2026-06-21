import React, { useState } from 'react';
import { motion } from 'motion/react';
import { X, UserPlus } from 'lucide-react';
import { Player } from '../types';

interface AddPlayerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onPlayerAdded: (player: Player) => void;
}

export default function AddPlayerModal({ isOpen, onClose, onPlayerAdded }: AddPlayerModalProps) {
  const [name, setName] = useState('');
  const [role, setRole] = useState<'Batter' | 'Bowler' | 'All-rounder' | 'WK-Batter'>('Batter');
  const [hand, setHand] = useState<'Right-hand bat' | 'Left-hand bat'>('Right-hand bat');
  const [province, setProvince] = useState('');
  const [jersey, setJersey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Please enter the player\'s full name.');
      return;
    }

    setLoading(true);
    setError('');

    const newPlayer: Omit<Player, 'id'> = {
      name: name.trim(),
      role,
      hand,
      province: province.trim() || 'Unassigned Club',
      jersey: jersey.trim() || 'N/A'
    };

    try {
      const response = await fetch('/api/players', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newPlayer)
      });

      if (!response.ok) {
        throw new Error('Failed to register player in the database.');
      }

      const savedPlayer = await response.json();
      onPlayerAdded(savedPlayer);
      setName('');
      setProvince('');
      setJersey('');
      onClose();
    } catch (err: any) {
      setError(err.message || 'Network error occurred.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-100 backdrop-blur-xs">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 15 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 15 }}
        className="bg-[#12161f] border border-[#252d3d] rounded-xl max-w-md w-full p-6 relative overflow-hidden"
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[#6b7593] hover:text-white bg-[#1a1f2e] border border-[#252d3d] w-8 h-8 rounded-md flex items-center justify-center transition-colors hover:cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-[#c8102e]/10 flex items-center justify-center text-[#c8102e]">
            <UserPlus className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-display uppercase tracking-widest text-[#e8eaf0]">Add Player</h2>
            <p className="text-xs text-[#6b7593]">Register a national player to the coaching system</p>
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
              Full Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Samjhana Khadka"
              disabled={loading}
              className="w-full bg-[#1a1f2e] border border-[#252d3d] text-[#e8eaf0] px-3 py-2 rounded-lg text-sm outline-none focus:border-[#c8102e] transition-colors"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-[#6b7593] mb-1.5">
                Role
              </label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as any)}
                disabled={loading}
                className="w-full bg-[#1a1f2e] border border-[#252d3d] text-[#e8eaf0] px-3 py-2 rounded-lg text-sm outline-none focus:border-[#c8102e] transition-colors hover:cursor-pointer"
              >
                <option value="Batter">Batter</option>
                <option value="Bowler">Bowler</option>
                <option value="All-rounder">All-rounder</option>
                <option value="WK-Batter">WK-Batter</option>
              </select>
            </div>

            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-[#6b7593] mb-1.5">
                Stance Batting
              </label>
              <select
                value={hand}
                onChange={(e) => setHand(e.target.value as any)}
                disabled={loading}
                className="w-full bg-[#1a1f2e] border border-[#252d3d] text-[#e8eaf0] px-3 py-2 rounded-lg text-sm outline-none focus:border-[#c8102e] transition-colors hover:cursor-pointer"
              >
                <option value="Right-hand bat">Right-hand bat</option>
                <option value="Left-hand bat">Left-hand bat</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-[#6b7593] mb-1.5">
                Province / Club
              </label>
              <input
                type="text"
                value={province}
                onChange={(e) => setProvince(e.target.value)}
                placeholder="e.g. Bagmati"
                disabled={loading}
                className="w-full bg-[#1a1f2e] border border-[#252d3d] text-[#e8eaf0] px-3 py-2 rounded-lg text-sm outline-none focus:border-[#c8102e] transition-colors"
              />
            </div>

            <div>
              <label className="block text-[10px] font-mono uppercase tracking-widest text-[#6b7593] mb-1.5">
                Jersey No.
              </label>
              <input
                type="text"
                value={jersey}
                onChange={(e) => setJersey(e.target.value)}
                placeholder="e.g. 7"
                disabled={loading}
                className="w-full bg-[#1a1f2e] border border-[#252d3d] text-[#e8eaf0] px-3 py-2 rounded-lg text-sm outline-none focus:border-[#c8102e] transition-colors"
              />
            </div>
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
              {loading ? 'Adding...' : 'Add Player'}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}
