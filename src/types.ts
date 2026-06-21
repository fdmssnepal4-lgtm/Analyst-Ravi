export interface Player {
  id: string;
  name: string;
  role: 'Batter' | 'Bowler' | 'All-rounder' | 'WK-Batter';
  hand: 'Right-hand bat' | 'Left-hand bat';
  province: string;
  jersey: string;
}

export interface Video {
  id: string;
  playerId: string;
  category: string;
  url: string;
  title: string;
  date: string;
  opposition: string;
  phase: string;
  notes: string;
  addedAt: number;
  department?: 'batting' | 'bowling';
}

export interface AICoachInsight {
  playerId: string;
  content: string;
  generatedAt: number;
}
