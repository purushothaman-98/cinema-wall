import { NextRequest, NextResponse } from 'next/server';
import { GoogleGenAI, Type } from "@google/genai";

async function generateWithRetry(ai: GoogleGenAI, params: any, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      return await ai.models.generateContent(params);
    } catch (error: any) {
      console.warn(`Attempt ${i + 1} failed: ${error.message}`);
      // Retry on rate limits (429) or service unavailable (503)
      if ((error.status === 429 || error.status === 503) && i < retries - 1) {
        const delay = 1000 * Math.pow(2, i); 
        await new Promise(r => setTimeout(r, delay));
        continue;
      }
      throw error;
    }
  }
}

export async function POST(req: NextRequest) {
  // Support both the standard API_KEY and the user's specific GEMINI_API_KEY defined in Vercel
  const apiKey = process.env.API_KEY || process.env.GEMINI_API_KEY;

  if (!apiKey) {
    return NextResponse.json({ 
      error: 'Server configuration error: process.env.API_KEY (or GEMINI_API_KEY) is missing. Please check your Vercel Environment Variables.' 
    }, { status: 500 });
  }

  try {
    const { movie, topics, sentiments, reviews } = await req.json();

    const prompt = `
      ANALYST TASK: Generate a deep consensus report for "${movie}".
      
      CONTEXT:
      - Scores: Critics ${sentiments.critics} / Audience ${sentiments.audience}
      - Key Themes: ${topics.join(', ')}
      - Sources:
      ${reviews.map((r: any) => `[${r.title}]: ${r.snippet}`).join('\n')}

      REQUIREMENTS (JSON ONLY):
      1. Tagline: Punchy, 1 sentence.
      2. Summary: High-level verdict (2 sentences).
      3. Critics vs Audience: Explicitly contrast their viewpoints.
      4. Conflict Matrix: Identify specific plot points where opinions diverge.
      5. Comment Vibe: 3 adjectives describing the mood.
    `;

    const ai = new GoogleGenAI({ apiKey: apiKey });

    const response = await generateWithRetry(ai, {
      model: "gemini-2.5-flash",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            tagline: { type: Type.STRING },
            summary: { type: Type.STRING },
            critics_vs_audience: { type: Type.STRING },
            conflict_points: { type: Type.STRING },
            comment_vibe: { type: Type.STRING }
          },
          required: ["tagline", "summary", "critics_vs_audience", "conflict_points", "comment_vibe"],
        }
      },
    });

    let text = response?.text || "{}";
    
    // CRITICAL FIX: Strip Markdown backticks if present
    text = text.replace(/```json/g, '').replace(/```/g, '').trim();

    return NextResponse.json(JSON.parse(text));

  } catch (error: any) {
    console.error('Summary API Error:', error);
    // Return the actual error message to the client for debugging
    const errorMessage = error.message || error.toString() || 'Unknown AI Error';
    return NextResponse.json({ error: errorMessage }, { status: 500 });
  }
}