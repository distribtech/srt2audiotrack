const { useState } = React;

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

function SubtitleRow({ sub, index, onChange, onDelete }) {
  const update = (field, value) => {
    onChange(index, { ...sub, [field]: value });
  };
  return (
    <tr className="hover:bg-gray-50">
      <td className="p-1 text-center">{index + 1}</td>
      <td className="p-1"><input className="border p-1 w-full" value={sub.start} onChange={e => update('start', e.target.value)} /></td>
      <td className="p-1"><input className="border p-1 w-full" value={sub.end} onChange={e => update('end', e.target.value)} /></td>
      <td className="p-1"><textarea className="border p-1 w-full" value={sub.text} onChange={e => update('text', e.target.value)} /></td>
      <td className="p-1 text-center"><button className="text-red-600" onClick={() => onDelete(index)}>Delete</button></td>
    </tr>
  );
}

function App() {
  const [subs, setSubs] = useState([]);
  const [videoSrc, setVideoSrc] = useState(null);

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
      {videoSrc && <video src={videoSrc} controls className="w-full mb-4" />}
      {subs.length > 0 && (
        <div className="table-wrapper">
          <table className="subtitle-table text-left">
            <thead className="table-header">
              <tr>
                <th>#</th>
                <th>Start</th>
                <th>End</th>
                <th>Text</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {subs.map((sub, i) => (
                <SubtitleRow key={i} sub={sub} index={i} onChange={updateSub} onDelete={deleteSub} />
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

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
