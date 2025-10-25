import { useState, useEffect } from 'react'
import axios from 'axios'
// import './App.css' // <- Hata veren satır kaldırıldı. Stiller aşağıya gömüldü.

const API_URL = "https://game-patch-api.onrender.com";

const SUPPORTED_GAMES = [
  "Valorant",
  "Roblox",
  "Minecraft",
  "League of Legends",
  "Counter-Strike 2",
  "Fortnite"
];

// YENİ: Tüm CSS stillerimizi içeren bileşen
const GlobalStyles = () => (
  <style>{`
    :root {
      font-family: Inter, system-ui, Avenir, Helvetica, Arial, sans-serif;
      background-color: #242424;
      color: rgba(255, 255, 255, 0.87);
    }
    body { margin: 0; }
    .container {
      max-width: 900px;
      margin: 0 auto;
      padding: 2rem;
    }
    header { 
      text-align: center; 
      border-bottom: 1px solid #555; 
      padding-bottom: 1rem; 
      margin-bottom: 2rem;
    }
    h1 { color: #535bf2; }
    .games-list h2, 
    .patch-details h2,
    .mode-selector h2 {
      border-bottom: 1px solid #444; 
      padding-bottom: 8px; 
    }
    .games-list, 
    .patch-details,
    .mode-selector {
      margin-top: 2rem;
    }
    .buttons { 
      display: flex; 
      flex-wrap: wrap; 
      gap: 10px; 
      margin-top: 1rem; 
    }
    .buttons button {
      padding: 10px 15px;
      border-radius: 8px;
      border: 1px solid transparent;
      font-weight: 500;
      background-color: #1a1a1a;
      color: rgba(255, 255, 255, 0.87);
      cursor: pointer;
      transition: border-color 0.25s;
    }
    .buttons button:hover { border-color: #535bf2; }
    .buttons button.active { background-color: #535bf2; color: white; }
    .loading, .error { 
      padding: 1rem; 
      border-radius: 8px; 
      margin-top: 1rem; 
    }
    .loading { background-color: #333; }
    .error { background-color: #4b2525; color: #ffbaba; }
    .json-output {
      background-color: #1a1a1a;
      border-radius: 8px;
      padding: 1rem;
      overflow-x: auto;
      margin-top: 1rem;
    }
    pre { margin: 0; }
    .history-controls { margin-bottom: 1rem; }
    .history-select {
      width: 100%;
      padding: 10px 15px;
      border-radius: 8px;
      border: 1px solid #555;
      font-weight: 500;
      background-color: #1a1a1a;
      color: rgba(255, 255, 255, 0.87);
      cursor: pointer;
      transition: border-color 0.25s;
      font-family: inherit;
      font-size: 1em;
    }
    .history-select:hover,
    .history-select:focus {
      border-color: #535bf2;
      outline: none;
    }
    /* --- Etki Skoru Stilleri --- */
    .impact-display {
      padding: 1rem;
      border-radius: 8px;
      margin-top: 1rem;
      font-size: 1.1em;
      font-weight: 500;
      text-align: center;
      border: 1px solid;
    }
    .impact-display span {
      margin-left: 10px;
      font-weight: bold;
    }
    .impact-küçük {
      background-color: #2a3a3a;
      border-color: #3fa8a8;
      color: #88f1f1;
    }
    .impact-orta {
      background-color: #4a4a2a;
      border-color: #a8a83f;
      color: #f1f188;
    }
    .impact-büyük {
      background-color: #4b2525;
      border-color: #a83f3f;
      color: #ffbaba;
    }
  `}</style>
);

// Skoru ve Etiketi gösterecek basit bir bileşen
const ImpactDisplay = ({ score, label }) => {
  if (score === undefined || score === null) {
    return null;
  }
  const impactClass = `impact-${label.toLowerCase()}`;
  const emoji = label === "Büyük" ? "🔥" : (label === "Orta" ? "⚠️" : "ℹ️");

  return (
    <div className={`impact-display ${impactClass}`}>
      <strong>{emoji} Yama Etki Skoru:</strong>
      <span>{label} ({score} / 10)</span>
    </div>
  );
}


function App() {
  const [mode, setMode] = useState('latest'); 
  const [selectedGame, setSelectedGame] = useState(SUPPORTED_GAMES[0]);
  const [patchData, setPatchData] = useState(null);
  const [archiveList, setArchiveList] = useState([]);
  const [selectedArchiveKey, setSelectedArchiveKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState(null);

  const formatTimestamp = (isoString) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString('tr-TR', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      });
    } catch (e) { return isoString; }
  }

  // HOOK 1 & 2: Oyun veya Mod değiştiğinde
  useEffect(() => {
    setPatchData(null);
    setError(null);
    setArchiveList([]);
    setSelectedArchiveKey("");

    if (mode === 'latest') {
      const fetchLatestPatch = async () => {
        setLoading(true);
        try {
          const response = await axios.get(`${API_URL}/public/patches`, {
            params: { game: selectedGame }
          });
          setPatchData(response.data);
        } catch (err) {
          setError(`Güncel veri çekilemedi: ${err.response?.data?.detail || err.message}`);
        }
        setLoading(false);
      };
      fetchLatestPatch();
    } else if (mode === 'history') {
      const fetchHistoryList = async () => {
        setLoadingHistory(true);
        try {
          const response = await axios.get(`${API_URL}/public/patches/history`, {
            params: { game: selectedGame }
          });
          setArchiveList(response.data.archives || []);
        } catch (err) {
          setError(`Arşiv listesi çekilemedi: ${err.response?.data?.detail || err.message}`);
        }
        setLoadingHistory(false);
      };
      fetchHistoryList();
    }
  }, [selectedGame, mode]);

  // HOOK 3: Arşiv tarihi seçildiğinde
  useEffect(() => {
    if (selectedArchiveKey && mode === 'history') {
      const fetchArchivedPatch = async () => {
        setLoading(true);
        setError(null);
        setPatchData(null);
        try {
          const response = await axios.get(`${API_URL}/public/patches/archive`, {
            params: { key: selectedArchiveKey }
          });
          setPatchData(response.data);
        } catch (err) {
          setError(`Arşivlenmiş veri çekilemedi: ${err.response?.data?.detail || err.message}`);
        }
        setLoading(false);
      };
      fetchArchivedPatch();
    }
  }, [selectedArchiveKey]);

  // --- JSX (Görsel Arayüz) ---
  return (
    <>
      {/* YENİ: Gömülü stilleri buraya ekliyoruz */}
      <GlobalStyles />
      
      <div className="container">
        <header>
          <h1>🎮 Game Patch Notes Intelligence API</h1>
          <p>En son oyun yamalarını analiz eden ve JSON formatında sunan API hizmeti.</p>
        </header>

        <main>
          {/* BÖLÜM 1: Oyunlar */}
          <section className="games-list">
            <h2>Desteklenen Oyunlar</h2>
            <div className="buttons">
              {SUPPORTED_GAMES.map((game) => (
                <button
                  key={game}
                  className={selectedGame === game ? 'active' : ''}
                  onClick={() => setSelectedGame(game)}
                >
                  {game}
                </button>
              ))}
            </div>
          </section>

          {/* BÖLÜM 2: Sekmeler */}
          <section className="mode-selector">
            <h2>Veri Görünümü</h2>
            <div className="buttons">
              <button
                className={mode === 'latest' ? 'active' : ''}
                onClick={() => setMode('latest')}
              >
                Son Güncel Yama
              </button>
              <button
                className={mode === 'history' ? 'active' : ''}
                onClick={() => setMode('history')}
              >
                Geçmiş Yamalar (Arşiv)
              </button>
            </div>
          </section>

          {/* BÖLÜM 3: Yama Detayları */}
          <section className="patch-details">
            <h2>
              {selectedGame} için 
              {mode === 'latest' ? ' Son Veri' : ' Geçmiş Veri'}
            </h2>
            
            {/* Tarih Seçici */}
            {mode === 'history' && (
              <div className="history-controls">
                {loadingHistory && <div className="loading">🔄 Arşiv listesi yükleniyor...</div>}
                {!loadingHistory && archiveList.length > 0 && (
                  <select 
                    className="history-select"
                    value={selectedArchiveKey}
                    onChange={(e) => setSelectedArchiveKey(e.target.value)}
                  >
                    <option value="">Lütfen bir arşiv tarihi seçin...</option>
                    {archiveList.map((archive) => (
                      <option key={archive.key} value={archive.key}>
                        {formatTimestamp(archive.date)} ({archive.size_kb} KB)
                      </option>
                    ))}
                  </select>
                )}
                {!loadingHistory && archiveList.length === 0 && !error && (
                  <div className="loading">Bu oyun için henüz bir arşiv kaydı bulunamadı.</div>
                )}
              </div>
            )}

            {/* Ana Veri Gösterim Alanı */}
            {loading && <div className="loading">🔄 Yama verisi yükleniyor...</div>}
            {error && <div className="error">❌ {error}</div>}

            {/* Etki Skoru Göstergesi */}
            {!loading && patchData && (
              <ImpactDisplay 
                score={patchData.impact_score} 
                label={patchData.impact_label} 
              />
            )}

            {/* JSON Verisi */}
            {patchData && (
              <div className="json-output">
                <pre>
                  <code>
                    {JSON.stringify(patchData, null, 2)}
                  </code>
                </pre>
              </div>
            )}

          </section>
        </main>
      </div>
    </>
  )
}

export default App

