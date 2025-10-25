import { useState, useEffect } from 'react'
import axios from 'axios'

// --- STİLLER DOĞRUDAN BURADA ---
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
    h2 {
      border-bottom: 1px solid #444; 
      padding-bottom: 8px; 
    }
    section { margin-top: 2rem; }
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
      background-color: #2a3a3a; border-color: #3fa8a8; color: #88f1f1;
    }
    .impact-orta {
      background-color: #4a4a2a; border-color: #a8a83f; color: #f1f188;
    }
    .impact-büyük {
      background-color: #4b2525; border-color: #a83f3f; color: #ffbaba;
    }

    /* --- YENİ: Formatlı Değişiklik Listesi Stilleri --- */
    .patch-changes-list {
      margin-top: 1.5rem;
      padding: 1rem;
      background-color: #1a1a1a;
      border-radius: 8px;
    }
    .patch-changes-list h3 {
      margin-top: 0.5rem;
      margin-bottom: 0.5rem;
      font-size: 1.2em;
    }
    .patch-changes-list ul {
      margin: 0;
      padding-left: 20px;
    }
    .patch-changes-list li {
      margin-bottom: 0.75rem;
    }
    .patch-changes-list strong {
      color: #a8a8ff; /* Hedef/Yetenek rengi */
    }
    .patch-changes-list .details {
      display: block;
      color: #ccc;
      margin-top: 2px;
      font-style: italic;
    }
    .change-group-buff h3 { color: #88f188; }
    .change-group-nerf h3 { color: #ffbaba; }
    .change-group-new h3 { color: #88d8f1; }
    .change-group-fix h3 { color: #f1f188; }
    .change-group-other h3 { color: #ccc; }
  `}</style>
);

// --- BİLEŞENLER ---

const ImpactDisplay = ({ score, label }) => {
  if (score === undefined || score === null) return null;
  const impactClass = `impact-${label.toLowerCase()}`;
  const emoji = label === "Büyük" ? "🔥" : (label === "Orta" ? "⚠️" : "ℹ️");
  return (
    <div className={`impact-display ${impactClass}`}>
      <strong>{emoji} Yama Etki Skoru:</strong>
      <span>{label} ({score} / 10)</span>
    </div>
  );
}

/**
 * YENİ: JSON'daki "changes" dizisini alan ve seçilen dile göre [cite: 1.1] 
 * güzel bir liste olarak gösteren bileşen.
 */
const PatchNotesDisplay = ({ changes, lang }) => {
  if (!changes || changes.length === 0) {
    return (
      <div className="patch-changes-list">
        <p>ℹ️ <i>Analiz tamamlandı ancak raporlanacak (nerf, buff, new, fix) önemli bir değişiklik bulunamadı.</i></p>
      </div>
    );
  }

  // Değişiklikleri tipe göre grupla (Telegram'daki gibi)
  const groups = { buff: [], nerf: [], new: [], fix: [], other: [] };
  changes.forEach(change => {
    const type = change.type?.toLowerCase() || 'other';
    if (type in groups) groups[type].push(change);
    else groups.other.push(change);
  });

  // Bir dil objesinden (veya eski string'den) metni güvenle çeker
  const getDetailText = (details) => {
    if (typeof details === 'object' && details !== null) {
      return details[lang] || details.tr || details.en || "Detay yok"; // İstenen dili, sonra TR, sonra EN dene
    }
    return details || "Detay yok"; // Eski veriler için (string ise)
  }

  // Grup başlıkları
  const groupTitles = {
    buff: "🟢 Güçlendirmeler (Buffs)",
    nerf: "🔴 Zayıflatmalar (Nerfs)",
    new: "✨ Yeni İçerik/Değişiklikler",
    fix: "🔧 Hata Düzeltmeleri (Fixes)",
    other: "📋 Diğer Değişiklikler"
  };

  return (
    <div className="patch-changes-list">
      {Object.entries(groups).map(([type, changesList]) => {
        if (changesList.length === 0) return null; // Boş grubu gösterme
        return (
          <div key={type} className={`change-group change-group-${type}`}>
            <h3>{groupTitles[type]}</h3>
            <ul>
              {changesList.map((change, index) => (
                <li key={index}>
                  <strong>
                    {change.target}
                    {change.ability && ` (${change.ability})`}
                  </strong>
                  <span className="details">
                    {getDetailText(change.details)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}


// --- ANA UYGULAMA BİLEŞENİ ---

const API_URL = "https://game-patch-api.onrender.com";
const SUPPORTED_GAMES = [
  "Valorant", "Roblox", "Minecraft", "League of Legends", "Counter-Strike 2", "Fortnite"
];

function App() {
  const [mode, setMode] = useState('latest'); 
  const [selectedGame, setSelectedGame] = useState(SUPPORTED_GAMES[0]);
  const [patchData, setPatchData] = useState(null);
  const [archiveList, setArchiveList] = useState([]);
  const [selectedArchiveKey, setSelectedArchiveKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState(null);
  
  // YENİ: Dil state'i [cite: 1.1]
  const [lang, setLang] = useState('tr'); // Varsayılan dil Türkçe

  const formatTimestamp = (isoString) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString('tr-TR', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      });
    } catch (e) { return isoString; }
  }

  // HOOK 1 & 2: Oyun veya Mod değiştiğinde (Değişiklik yok)
  useEffect(() => {
    setPatchData(null);
    setError(null);
    setArchiveList([]);
    setSelectedArchiveKey("");
    if (mode === 'latest') {
      const fetchLatestPatch = async () => {
        setLoading(true);
        try {
          const response = await axios.get(`${API_URL}/public/patches`, { params: { game: selectedGame } });
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
          const response = await axios.get(`${API_URL}/public/patches/history`, { params: { game: selectedGame } });
          setArchiveList(response.data.archives || []);
        } catch (err) {
          setError(`Arşiv listesi çekilemedi: ${err.response?.data?.detail || err.message}`);
        }
        setLoadingHistory(false);
      };
      fetchHistoryList();
    }
  }, [selectedGame, mode]);

  // HOOK 3: Arşiv tarihi seçildiğinde (Değişiklik yok)
  useEffect(() => {
    if (selectedArchiveKey && mode === 'history') {
      const fetchArchivedPatch = async () => {
        setLoading(true);
        setError(null);
        setPatchData(null);
        try {
          const response = await axios.get(`${API_URL}/public/patches/archive`, { params: { key: selectedArchiveKey } });
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

          {/* BÖLÜM 2: Dil ve Mod Seçiciler */}
          <section className="controls">
            <div className="mode-selector">
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
            </div>
            
            {/* YENİ: Dil Seçici [cite: 1.1] */}
            <div className="language-selector" style={{marginTop: '1.5rem'}}>
              <h2>Özet Dili</h2>
              <div className="buttons">
                <button
                  className={lang === 'tr' ? 'active' : ''}
                  onClick={() => setLang('tr')}
                >
                  🇹🇷 Türkçe
                </button>
                <button
                  className={lang === 'en' ? 'active' : ''}
                  onClick={() => setLang('en')}
                >
                  🇬🇧 English
                </button>
              </div>
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
                    onChange={(e) => setSelectedArchiveKey(e.taget.value)}
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

            {/* Veri yüklendiğinde ve hata olmadığında */}
            {!loading && patchData && (
              <>
                {/* 1. Etki Skoru Göstergesi */}
                <ImpactDisplay 
                  score={patchData.impact_score} 
                  label={patchData.impact_label} 
                />
                
                {/* 2. YENİ: Formatlı Değişiklik Listesi */}
                <PatchNotesDisplay 
                  changes={patchData.changes} 
                  lang={lang} 
                />

                {/* 3. Ham JSON Çıktısı (Teknik kullanıcılar için) */}
                <h3 style={{marginTop: '2rem'}}>Raw JSON Output:</h3>
                <div className="json-output">
                  <pre>
                    <code>
                      {JSON.stringify(patchData, null, 2)}
                    </code>
                  </pre>
                </div>
              </>
            )}
          </section>
        </main>
      </div>
    </>
  )
}

export default App

