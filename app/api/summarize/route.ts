import { NextRequest, NextResponse } from 'next/server';
import { GoogleGenAI, Type } from "@google/genai";

export async function POST(req: NextRequest) {
  // Support both variable names just in case
  const apiKey = process.env.GEMINI_API_KEY || process.env.API_KEY;

  if (!apiKey) {
    console.error("Missing GEMINI_API_KEY");
    return NextResponse.json({ error: 'Server configuration error: Missing AI Key' }, { status: 500 });
  }

  try {
    const { movie, topics, sentiments, reviews } = await req.json();

    const prompt = `
      You are a film analyst. Summarize the critical consensus for the movie "${movie}".
      
      Data points:
      - Key topics: ${topics.join(', ')}
      - Sentiment distribution: ${sentiments}
      - Review excerpts: 
      ${reviews.map((r: any) => `- ${r.title}: ${r.snippet}`).join('\n')}

      Create a short punchy consensus tagline and a detailed paragraph summary.
    `;

    const ai = new GoogleGenAI({ apiKey: apiKey });

    // Guidelines: Use 'gemini-3-flash-preview' for Basic Text Tasks
    const response = await ai.models.generateContent({
      model: "gemini-3-flash-preview",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            tagline: { type: Type.STRING },
            summary: { type: Type.STRING },
          },
          required: ["tagline", "summary"],
        }
      },
    });

    const text = response.text;
    
    if (!text) throw new Error("No response text from AI");

    return NextResponse.json(JSON.parse(text));

  } catch (error) {
    console.error('Summary API Error:', error);
    return NextResponse.json({ error: 'Failed to generate summary' }, { status: 500 });
  }
}