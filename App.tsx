'use client';

import React, { useMemo, useState } from 'react';

type Platform = 'All sources' | 'YouTube' | 'Reddit';

type Film = {
  title: string;
  year: number;
  score: number;
  youtube: number;
  reddit: number;
  mentions: number;
  positive: number;
  neutral: number;
  negative: number;
  trend: number[];
  topics: { label: string; score: number }[];
  verdict: string;
  accent: string;
  tamil: string;
};

const films: Film[] = [
  { title: 'Tourist Family', tamil: 'டூரிஸ்ட் ஃபேமிலி', year: 2025, score: 91, youtube: 93, reddit: 86, mentions: 18420, positive: 86, neutral: 9, negative: 5, trend: [55,64,72,78,83,89,91], verdict: 'Warm crowd favourite', accent: '#f6c85f', topics: [{label:'Story',score:94},{label:'Acting',score:91},{label:'Emotion',score:96}] },
  { title: 'Dragon', tamil: 'டிராகன்', year: 2025, score: 84, youtube: 88, reddit: 76, mentions: 26980, positive: 79, neutral: 13, negative: 8, trend: [61,72,81,86,83,84,84], verdict: 'Youthful & highly engaging', accent: '#ff6b4a', topics: [{label:'Comedy',score:91},{label:'Acting',score:84},{label:'Screenplay',score:79}] },
  { title: 'Good Bad Ugly', tamil: 'குட் பேட் அக்லி', year: 2025, score: 77, youtube: 84, reddit: 63, mentions: 34120, positive: 70, neutral: 16, negative: 14, trend: [86,88,82,75,72,75,77], verdict: 'Big fan celebration', accent: '#db4b7a', topics: [{label:'Fan moments',score:96},{label:'Music',score:81},{label:'Story',score:57}] },
  { title: 'Retro', tamil: 'ரெட்ரோ', year: 2025, score: 72, youtube: 75, reddit: 67, mentions: 22160, positive: 63, neutral: 20, negative: 17, trend: [79,81,74,69,68,71,72], verdict: 'Stylish, but divisive', accent: '#58b09c', topics: [{label:'Visuals',score:93},{label:'Music',score:86},{label:'Pacing',score:51}] },
  { title: 'Vidaamuyarchi', tamil: 'விடாமுயற்சி', year: 2025, score: 65, youtube: 70, reddit: 56, mentions: 29840, positive: 54, neutral: 23, negative: 23, trend: [82,76,68,63,61,64,65], verdict: 'Mixed road thriller', accent: '#7c83fd', topics: [{label:'Performance',score:78},{label:'Visuals',score:73},{label:'Pacing',score:46}] },
  { title: 'Thug Life', tamil: 'தக் லைஃப்', year: 2025, score: 48, youtube: 52, reddit: 39, mentions: 31750, positive: 35, neutral: 26, negative: 39, trend: [78,71,59,48,44,46,48], verdict: 'Expectations divided', accent: '#d85d5d', topics: [{label:'Acting',score:74},{label:'Music',score:69},{label:'Writing',score:35}] },
];

const number = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 });

function scoreFor(film: Film, platform: Platform) {
  return platform === 'YouTube' ? film.youtube : platform === 'Reddit' ? film.reddit : film.score;
}

function Sparkline({ values, color }: { values: number[]; color: string }) {
  const points = values.map((value, index) => `${(index / (values.length - 1)) * 100},${42 - ((value - 35) / 65) * 38}`).join(' ');
  return (
    <svg viewBox="0 0 100 44" className="spark" aria-label="Seven day sentiment trend">
      <path d="M0 42H100" className="spark-grid" />
      <polyline points={points} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="100" cy={points.split(' ').at(-1)?.split(',')[1]} r="3.2" fill={color} />
    </svg>
  );
}

function App() {
  const [platform, setPlatform] = useState<Platform>('All sources');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(films[0]);
  const [sort, setSort] = useState<'sentiment' | 'mentions'>('sentiment');

  const visible = useMemo(() => films
    .filter(f => `${f.title} ${f.tamil}`.toLowerCase().includes(query.toLowerCase()))
    .sort((a,b) => sort === 'mentions' ? b.mentions - a.mentions : scoreFor(b, platform) - scoreFor(a, platform)), [platform, query, sort]);

  const totalMentions = films.reduce((sum, film) => sum + film.mentions, 0);
  const avgScore = Math.round(films.reduce((sum, film) => sum + scoreFor(film, platform), 0) / films.length);

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Tamil Film Pulse home"><span className="brand-mark">தி</span><span>TAMIL FILM <b>PULSE</b></span></a>
        <nav><a href="#rankings">Rankings</a><a href="#compare">Compare</a><a href="#method">Method</a></nav>
        <div className="live-pill"><i /> DEMO DATA</div>
      </header>

      <section className="hero" id="top">
        <div>
          <p className="eyebrow">THE AUDIENCE, MEASURED</p>
          <h1>What is Tamil cinema<br/><em>really</em> feeling?</h1>
          <p className="lede">A single, transparent view of conversations across YouTube and Reddit—built for Tamil, Tanglish and English reactions.</p>
        </div>
        <div className="hero-metrics">
          <div><span>FILMS TRACKED</span><strong>{films.length}</strong><small>Recent releases</small></div>
          <div><span>PUBLIC MENTIONS</span><strong>{number.format(totalMentions)}</strong><small>Demonstration dataset</small></div>
          <div><span>MOOD INDEX</span><strong>{avgScore}</strong><small className="up">↑ broadly positive</small></div>
        </div>
      </section>

      <section className="controls" id="rankings">
        <div className="platform-tabs" role="group" aria-label="Choose a source">
          {(['All sources','YouTube','Reddit'] as Platform[]).map(item => <button key={item} onClick={() => setPlatform(item)} className={platform === item ? 'active' : ''}>{item}</button>)}
        </div>
        <label className="search"><span>⌕</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search films / திரைப்படம் தேடுக" /></label>
        <select value={sort} onChange={e => setSort(e.target.value as 'sentiment'|'mentions')} aria-label="Sort films"><option value="sentiment">Highest sentiment</option><option value="mentions">Most discussed</option></select>
      </section>

      <section className="dashboard-grid">
        <div className="ranking-panel">
          <div className="section-title"><div><p>LIVE LEADERBOARD</p><h2>Film sentiment ranking</h2></div><span>Score / 100</span></div>
          <div className="film-list">
            {visible.map((film, index) => {
              const score = scoreFor(film, platform);
              return <button key={film.title} className={`film-row ${selected.title === film.title ? 'selected' : ''}`} onClick={() => setSelected(film)}>
                <span className="rank">{String(index + 1).padStart(2,'0')}</span>
                <span className="poster" style={{'--accent': film.accent} as React.CSSProperties}><b>{film.title.split(' ').map(w=>w[0]).join('').slice(0,3)}</b></span>
                <span className="film-name"><b>{film.title}</b><small>{film.tamil} · {number.format(film.mentions)} mentions</small></span>
                <span className="mini-trend"><Sparkline values={film.trend} color={film.accent}/></span>
                <span className={`score ${score >= 75 ? 'good' : score < 55 ? 'poor' : ''}`}>{score}</span>
              </button>
            })}
          </div>
          {visible.length === 0 && <div className="empty">No matching film found.</div>}
        </div>

        <aside className="detail-panel" id="compare">
          <div className="detail-head"><div><p>SELECTED FILM</p><h2>{selected.title}</h2><span>{selected.tamil}</span></div><div className="big-score" style={{'--score': `${selected.score * 3.6}deg`} as React.CSSProperties}><b>{selected.score}</b><small>Pulse</small></div></div>
          <p className="verdict">“{selected.verdict}”</p>
          <div className="platform-compare">
            <div><span><b className="youtube-dot"/>YouTube</span><strong>{selected.youtube}</strong><i><b style={{width:`${selected.youtube}%`}}/></i></div>
            <div><span><b className="reddit-dot"/>Reddit</span><strong>{selected.reddit}</strong><i><b style={{width:`${selected.reddit}%`}}/></i></div>
          </div>
          <div className="sentiment-split">
            <p>SENTIMENT MIX</p>
            <div className="split-bar"><i style={{width:`${selected.positive}%`}}/><i style={{width:`${selected.neutral}%`}}/><i style={{width:`${selected.negative}%`}}/></div>
            <div className="legend"><span><b className="pos"/>{selected.positive}% Positive</span><span><b className="neu"/>{selected.neutral}% Neutral</span><span><b className="neg"/>{selected.negative}% Negative</span></div>
          </div>
          <div className="topics"><p>WHAT PEOPLE TALK ABOUT</p>{selected.topics.map(topic => <div key={topic.label}><span>{topic.label}</span><i><b style={{width:`${topic.score}%`}}/></i><strong>{topic.score}</strong></div>)}</div>
        </aside>
      </section>

      <section className="method" id="method">
        <div><p>HOW TO READ THIS</p><h2>Conversation, not a verdict.</h2></div>
        <p>The dashboard separates platform scores and shows the share of positive, neutral and negative reactions. Demonstration values are used until the YouTube and Reddit collectors are connected.</p>
        <div className="method-steps"><span><b>01</b>Collect public comments</span><span><b>02</b>Detect Tamil + Tanglish</span><span><b>03</b>Remove spam and duplicates</span><span><b>04</b>Score sentiment + topics</span></div>
      </section>
      <footer><span>TAMIL FILM PULSE · OPEN SENTIMENT DASHBOARD</span><span>Public discussion analysis · Not a box-office rating</span></footer>
    </main>
  );
}

export default App;
