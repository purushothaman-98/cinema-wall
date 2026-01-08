
import { NextRequest, NextResponse } from 'next/server';
import { GoogleGenAI, Type } from "@google/genai";

// Retry helper for Free Tier Rate Limits (429)
async function generateWithRetry(ai: GoogleGenAI, params: any, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      return await ai.models.generateContent(params);
    } catch (error: any) {
      // Check for Rate Limit (429) or Service Unavailable (503)
      if ((error.status === 429 || error.status === 503) && i < retries - 1) {
        const delay = 1000 * Math.pow(2, i); // Exponential backoff: 1s, 2s, 4s
        console.warn(`Gemini Rate Limit hit. Retrying in ${delay}ms...`);
        await new Promise(r => setTimeout(r, delay));
        continue;
      }
      throw error;
    }
  }
}

export async function POST(req: NextRequest) {
  const apiKey = process.env.GEMINI_API_KEY || process.env.API_KEY;

  if (!apiKey) {
    return NextResponse.json({ error: 'Server configuration error: Missing AI Key' }, { status: 500 });
  }

  try {
    const { movie, topics, sentiments, reviews } = await req.json();

    // optimized prompt to save input tokens while asking for depth
    const prompt = `
      ANALYST TASK: Generate a deep consensus report for "${movie}".
      
      CONTEXT:
      - Scores: Critics ${sentiments.critics} / Audience ${sentiments.audience}
      - Key Themes: ${topics.join(', ')}
      - Sources:
      ${reviews.map((r: any) => `[${r.title}]: ${r.snippet}`).join('\n')}

      REQUIREMENTS:
      1. Tagline: Punchy, 1 sentence.
      2. Summary: High-level verdict (2 sentences).
      3. Critics vs Audience: Explicitly contrast their viewpoints. Do they agree? If not, why?
      4. Conflict Matrix: Identify specific plot points, acting, or technical elements where reviewers disagree.
      5. Comment Vibe: 3-5 adjectives describing the emotional state of the comment section (e.g., "Toxic," "Hype," "Confused").
    `;

    const ai = new GoogleGenAI({ apiKey: apiKey });

    // Use gemini-3-flash-preview for speed and efficiency
    const response = await generateWithRetry(ai, {
      model: "gemini-3-flash-preview",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            tagline: { type: Type.STRING },
            summary: { type: Type.STRING },
            critics_vs_audience: { type: Type.STRING, description: "Analysis of the gap between professional and casual viewers." },
            conflict_points: { type: Type.STRING, description: "Specific elements (plot/acting) where opinions diverge." },
            comment_vibe: { type: Type.STRING, description: "Short description of the community mood." }
          },
          required: ["tagline", "summary", "critics_vs_audience", "conflict_points", "comment_vibe"],
        }
      },
    });

    const text = response?.text;
    
    if (!text) throw new Error("No response text from AI");

    return NextResponse.json(JSON.parse(text));

  } catch (error) {
    console.error('Summary API Error:', error);
    return NextResponse.json({ error: 'Failed to generate summary' }, { status: 500 });
  }
}
