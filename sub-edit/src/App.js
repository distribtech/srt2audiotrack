import React, { useState, useRef } from 'react';
import './App.css';

function parseSRT(text) {
  const subs = [];
  const lines = text.trim().replace(/\r/g, '').split(/\n/);
  let i = 0;
  while (i < lines.length) {
    if (!/^\d+$/.test(lines[i]?.trim())) { i++; continue; }
    const index = parseInt(lines[i].trim(), 10); i++;
    if (!lines[i]?.includes('-->')) { continue; }
    const [start, end] = lines[i].trim().split(' --> ').map(t => t.trim());
    i++;
    let textLines = [];
    while (i < lines.length && lines[i].trim() !== '') {
      textLines.push(lines[i].trim());
      i++;
    }
    subs.push({ index, start, end, text: textLines.join('\n') });
    while (i < lines.length && lines[i].trim() === '') { i++; }
  }
  return subs;
}

function toSRT(subs) {
  return subs.map((s, idx) => `${idx + 1}\n${s.start} --> ${s.end}\n${s.text}\n`).join('\n');
}

function timeToSeconds(timeStr) {
  if (!timeStr) return 0;
  const parts = timeStr.split(/[:,]/);
  if (parts.length !== 4) return 0;
  return (
    parseInt(parts[0], 10) * 3600 +
    parseInt(parts[1], 10) * 60 +
    parseInt(parts[2], 10) +
    parseInt(parts[3], 10) / 1000
  );
}

function secondsToTime(seconds) {
  if (isNaN(seconds) || seconds < 0) return '00:00:00,000';
  const h = Math.floor(seconds / 3600)
    .toString()
    .padStart(2, '0');
  const m = Math.floor((seconds % 3600) / 60)
    .toString()
    .padStart(2, '0');
  const s = Math.floor(seconds % 60)
    .toString()
    .padStart(2, '0');
  const ms = Math.round((seconds - Math.floor(seconds)) * 1000)
    .toString()
    .padStart(3, '0');
  return `${h}:${m}:${s},${ms}`;
}

function SubtitleRow({
  sub,
  index,
  onChange,
  onDelete,
  onPlay,
  onPlayFromStart,
  onSplit,
  onSetStart,
  onSetEnd,
  onMerge
}) {
  const update = (field, value) => {
    onChange(index, { ...sub, [field]: value });
  };
  return (
    <tr className="hover:bg-gray-50">
      <td className="p-1 text-center">{index + 1}</td>
      <td className="p-1"><input className="border p-1 w-full" value={sub.start} onChange={e => update('start', e.target.value)} /></td>
      <td className="p-1"><input className="border p-1 w-full" value={sub.end} onChange={e => update('end', e.target.value)} /></td>
      <td className="p-1"><textarea className="border p-1 w-full" value={sub.text} onChange={e => update('text', e.target.value)} /></td>
      <td className="p-1 text-center"><button className="text-blue-600" onClick={onPlay}>▶/❚❚</button></td>
      <td className="p-1 text-center"><button className="text-purple-600" onClick={onPlayFromStart}>▶▶</button></td>
      <td className="p-1 text-center"><button className="text-orange-600" onClick={onSplit}>Split</button></td>
      <td className="p-1 text-center space-x-1">
        <button className="text-green-600" onClick={onSetStart}>S</button>
        <button className="text-green-600" onClick={onSetEnd}>E</button>
        <button className="text-yellow-600" onClick={onMerge}>Merge</button>
        <button className="text-red-600" onClick={() => onDelete(index)}>X</button>
      </td>
    </tr>
  );
}

function App() {
  const [subs, setSubs] = useState([]);
  const [videoSrc, setVideoSrc] = useState(null);
  const videoRef = useRef(null);

  const handleSrtUpload = e => {
    const file = e.target.files[0];
    if (!file) return;
    file.text().then(txt => setSubs(parseSRT(txt)));
  };

  const handleVideoUpload = e => {
    const file = e.target.files[0];
    if (!file) return;
    setVideoSrc(URL.createObjectURL(file));
  };

  const updateSub = (idx, newSub) => {
    const next = subs.slice();
    next[idx] = newSub;
    setSubs(next);
  };

  const deleteSub = idx => {
    setSubs(subs.filter((_, i) => i !== idx));
  };

  const setStart = idx => {
    if (!videoRef.current) return;
    const next = subs.slice();
    next[idx].start = secondsToTime(videoRef.current.currentTime);
    setSubs(next);
  };

  const setEnd = idx => {
    if (!videoRef.current) return;
    const next = subs.slice();
    next[idx].end = secondsToTime(videoRef.current.currentTime);
    setSubs(next);
  };

  const playSubtitle = idx => {
    if (!videoRef.current) return;
    const start = timeToSeconds(subs[idx].start);
    const end = timeToSeconds(subs[idx].end);
    videoRef.current.currentTime = start;
    videoRef.current.play();
    const onUpdate = () => {
      if (videoRef.current.currentTime >= end) {
        videoRef.current.pause();
        videoRef.current.removeEventListener('timeupdate', onUpdate);
      }
    };
    videoRef.current.addEventListener('timeupdate', onUpdate);
  };

  const playFromStart = idx => {
    if (!videoRef.current) return;
    videoRef.current.currentTime = timeToSeconds(subs[idx].start);
    videoRef.current.play();
  };

  const mergeWithNext = idx => {
    if (idx >= subs.length - 1) return;
    const merged = subs.slice();
    merged[idx] = {
      ...merged[idx],
      end: merged[idx + 1].end,
      text: `${merged[idx].text}\n${merged[idx + 1].text}`
    };
    merged.splice(idx + 1, 1);
    setSubs(merged);
  };

  const splitSubtitle = idx => {
    if (!videoRef.current) return;
    const current = videoRef.current.currentTime;
    const start = timeToSeconds(subs[idx].start);
    const end = timeToSeconds(subs[idx].end);
    if (current <= start || current >= end) return;
    const text = subs[idx].text;
    const mid = Math.floor(text.length / 2);
    const first = text.slice(0, mid).trim();
    const second = text.slice(mid).trim();
    const nextSubs = subs.slice();
    nextSubs[idx] = { ...nextSubs[idx], end: secondsToTime(current), text: first };
    nextSubs.splice(idx + 1, 0, {
      start: secondsToTime(current),
      end: secondsToTime(end),
      text: second
    });
    setSubs(nextSubs);
  };

  const addLine = () => {
    setSubs([...subs, { start: '00:00:00,000', end: '00:00:00,000', text: '' }]);
  };

  const saveSrt = () => {
    const blob = new Blob([toSRT(subs)], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'subtitles.srt';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="container mx-auto p-4 md:p-8">
      <h1 className="text-2xl font-bold mb-4">Subtitle Editor</h1>
      <div className="mb-4 space-y-2">
        <div>
          <label className="mr-2">Subtitle File:</label>
          <input type="file" accept=".srt" onChange={handleSrtUpload} />
        </div>
        <div>
          <label className="mr-2">Media File:</label>
          <input type="file" accept="video/*,audio/*" onChange={handleVideoUpload} />
        </div>
      </div>
      {videoSrc && (
        <video ref={videoRef} src={videoSrc} controls className="w-full mb-4" />
      )}
      {subs.length > 0 && (
        <div className="table-wrapper">
          <table className="subtitle-table text-left">
            <thead className="table-header">
              <tr>
                <th>#</th>
                <th>Start</th>
                <th>End</th>
                <th>Text</th>
                <th>Play/Stop</th>
                <th>Play from Start</th>
                <th>Split</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {subs.map((sub, i) => (
                <SubtitleRow
                  key={i}
                  sub={sub}
                  index={i}
                  onChange={updateSub}
                  onDelete={deleteSub}
                  onPlay={() => playSubtitle(i)}
                  onPlayFromStart={() => playFromStart(i)}
                  onSplit={() => splitSubtitle(i)}
                  onSetStart={() => setStart(i)}
                  onSetEnd={() => setEnd(i)}
                  onMerge={() => mergeWithNext(i)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="mt-4 space-x-2">
        <button className="bg-indigo-500 hover:bg-indigo-600 text-white font-bold py-2 px-4 rounded" onClick={addLine}>Add Line</button>
        <button className="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded" onClick={saveSrt}>Save</button>
      </div>
    </div>
  );
}

export default App;
