import express from "express";
import path from "path";
import fs from "fs";
import { createServer as createViteServer } from "vite";
import { GoogleGenAI } from "@google/genai";
import dotenv from "dotenv";

dotenv.config();

async function startServer() {
  const app = express();
  app.use(express.json());
  const PORT = 3000;

  // Local JSON state database path
  const DB_PATH = path.join(process.cwd(), "db.json");

  function readDB() {
    if (!fs.existsSync(DB_PATH)) {
      const initialData = {
        players: [
          { id: 'p1', name: 'Samjhana Khadka', role: 'All-rounder', hand: 'Right-hand bat', province: 'Karnali', jersey: '7' },
          { id: 'p2', name: 'Indu Barma', role: 'Batter', hand: 'Right-hand bat', province: 'Armed Police Force', jersey: '19' },
          { id: 'p3', name: 'Kabita Kunwar', role: 'Bowler', hand: 'Right-hand bat', province: 'APF Club', jersey: '11' },
          { id: 'p4', name: 'Rubina Chhetri', role: 'All-rounder', hand: 'Right-hand bat', province: 'Bagmati', jersey: '1' }
        ],
        videos: [
          {
            id: 'v1',
            playerId: 'p1',
            category: 'strength',
            url: 'https://www.youtube.com/watch?v=kYJbyF4iG2g',
            title: 'Driving cleanly through the extra-cover region',
            date: 'Asia Cup - vs UAE',
            opposition: 'UAE',
            phase: 'Powerplay (1-6)',
            notes: 'Showcasing spectacular high-elbow presentation. Key notes: weight transfers fully onto the front foot, keeping the ball grounded. Great pacing.',
            addedAt: Date.now() - 5000000
          },
          {
            id: 'v2',
            playerId: 'p1',
            category: 'weakness',
            url: 'https://www.youtube.com/watch?v=yK8ZkM-Z_qA',
            title: 'Vulnerability to short ball in defensive block',
            date: 'Squad T20 Warm-up',
            opposition: 'Nepal Red',
            phase: 'Middle (7-15)',
            notes: 'Closing the hips too fast against steep bounce. Training drills are set to focus on playing on the back-foot and rolling the wrist down.',
            addedAt: Date.now() - 4000000
          },
          {
            id: 'v3',
            playerId: 'p2',
            category: 'boundary',
            url: 'https://www.youtube.com/watch?v=kYJbyF4iG2g',
            title: 'Lofted straight drive over bowler head',
            date: 'Live Game Highlights',
            opposition: 'Malaysia',
            phase: 'Death (16-20)',
            notes: 'Fantastic extension of the arms here. Clears the front leg and follows through fully to clear the fielders with ease.',
            addedAt: Date.now() - 3000000
          },
          {
            id: 'v4',
            playerId: 'p3',
            category: 'pace',
            url: 'https://www.youtube.com/watch?v=yK8ZkM-Z_qA',
            title: 'Inswinging delivery breaking middle stump',
            date: 'Practice Session',
            opposition: 'Spin squad',
            phase: 'Powerplay (1-6)',
            notes: 'Lovely release angle. The ball pitches at good length and shapes in beautifully, targeting the corridor of uncertainty.',
            addedAt: Date.now() - 2000000
          }
        ]
      };
      fs.writeFileSync(DB_PATH, JSON.stringify(initialData, null, 2));
      return initialData;
    }
    try {
      return JSON.parse(fs.readFileSync(DB_PATH, "utf8"));
    } catch (e) {
      console.error("Database parsing failed, regenerating standard templates");
      return { players: [], videos: [] };
    }
  }

  function writeDB(data: any) {
    fs.writeFileSync(DB_PATH, JSON.stringify(data, null, 2));
  }

  // API Endpoints
  app.get("/api/db", (req, res) => {
    try {
      res.json(readDB());
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.post("/api/players", (req, res) => {
    try {
      const db = readDB();
      const newPlayer = req.body;
      if (!newPlayer.id) {
        newPlayer.id = 'p' + Date.now();
      }
      db.players.push(newPlayer);
      writeDB(db);
      res.status(201).json(newPlayer);
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.delete("/api/players/:id", (req, res) => {
    try {
      const db = readDB();
      const { id } = req.params;
      db.players = db.players.filter((p: any) => p.id !== id);
      db.videos = db.videos.filter((v: any) => v.playerId !== id);
      writeDB(db);
      res.json({ success: true });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.post("/api/videos", (req, res) => {
    try {
      const db = readDB();
      const newVideo = req.body;
      if (!newVideo.id) {
        newVideo.id = 'v' + Date.now() + Math.random().toString(36).slice(2, 6);
      }
      db.videos.push(newVideo);
      writeDB(db);
      res.status(201).json(newVideo);
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.delete("/api/videos/:id", (req, res) => {
    try {
      const db = readDB();
      const { id } = req.params;
      db.videos = db.videos.filter((v: any) => v.id !== id);
      writeDB(db);
      res.json({ success: true });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // AI Assistant Analysis using Gemini API
  app.post("/api/gemini/coaching-tips", async (req, res) => {
    try {
      const { player, videos } = req.body;
      if (!player) {
        return res.status(400).json({ error: "Missing player details" });
      }

      const apiKey = process.env.GEMINI_API_KEY;
      if (!apiKey) {
        return res.status(500).json({ error: "Gemini API Key is not configured. Please supply a valid key under the Settings secrets panel." });
      }

      const ai = new GoogleGenAI({
        apiKey: apiKey,
        httpOptions: {
          headers: {
            "User-Agent": "aistudio-build",
          },
        },
      });

      const videoLogsText = (videos && videos.length > 0)
        ? videos.map((v: any, idx: number) => `
Video #${idx + 1}:
- Title: ${v.title}
- Category Tag: ${v.category.toUpperCase()}
- Opponent / Venue: ${v.opposition || "N/A"}
- Match Phase: ${v.phase || "N/A"}
- Date / Context: ${v.date || "N/A"}
- Coach Insights & Observations: ${v.notes || "None recorded"}
        `).join("\n")
        : "No tactical video analysis logs compiled yet for this user.";

      const prompt = `You are the Lead High-Performance Coach and Strategic Tactical Analyst of the Nepal Women's National Cricket Team (Team Nepal / "The Lady Rhinos"). You have an extensive background in elite cricket analysis.

You are compiling a comprehensive Strategic Performance Briefing specifically tailored for the following player:
- Name: ${player.name}
- Team Role: ${player.role}
- Batting/Bowling Style: ${player.hand}
- Jersey Number: #${player.jersey || "N/A"}
- Region/Province Association: ${player.province || "N/A"}

Here are the compiled video sessions and specific coaching notes related to this player:
${videoLogsText}

Please generate an expert High-Performance Cricket Tactical Report in Markdown. Address her directly or refer to her with immense respect for her contribution to Nepal's cricket journey. Balance strict technical micro-analyses of her mechanics with highly motivational sports leadership tone.

Ensure your analysis contains the following exact sections with outstanding formatting and structured layout:

1. 📈 **PERFORMANCE SYNERGY & MATCHUP INSIGHTS**
Synthesize her overall capabilities as an elite player. Explain how her recorded strengths fit within her role as a ${player.role}. Ground the analysis with specific mentions of her team contribution or province style (${player.province}) to keep it highly personalized to Nepal Women's cricket context.

2. 🚨 **CORE TECH WEAKNESS DRILL BLUEPRINT**
Directly identify from the log any tagged structural flaws/weaknesses. Prescribe a rigorous, technical mechanical drill routine (specifying throw-downs, turf setups, and bowl machine parameters). Outline exactly how to correct her stance posture, alignment, wrist orientation, and back-lift to address the issues.

3. ⚔️ **TACTICAL MATCHPLAY BLUEPRINT**
Outline an intensive, phase-by-phase tactical blueprint for three crucial game scenarios:
- **Powerplay (Overs 1-6)**: Gap utilization, taking aerial leverage, or pacing risk.
- **Middle Overs (Overs 7-15)**: Strategic sweep shots, strike rotation, running between wickets to eliminate Dot Balls.
- **Death Overs (Overs 16-20)**: Full follow-through swings, bat-speed drills, and boundary hunting rules.

Make the output incredibly rich and detailed, avoiding plain generic statements. Utilize bold cricket terms (such as 'high elbow presentation', 'corridor of uncertainty', 'sweet spot activation', 'stance stability plane') to emphasize high authenticity.`;

      const response = await ai.models.generateContent({
        model: "gemini-3.5-flash",
        contents: prompt,
      });

      res.json({ content: response.text });
    } catch (err: any) {
      console.error("Gemini server error:", err);
      res.status(500).json({ error: err.message || "Failed to contact Gemini engine." });
    }
  });

  // Serve static assets or use Vite dev server
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server started successfully on port ${PORT}`);
  });
}

startServer();
