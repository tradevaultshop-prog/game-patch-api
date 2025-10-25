import { useState, useEffect } from "react";
import axios from "axios";

// --- DİL ÇEVİRİ OBJESİ (GÜNCELLENDİ) ---
const i18n = {
  tr: {
    headerTitle: "🎮 Game Patch Notes Intelligence API",
    headerSubtitle:
      "En son oyun yamalarını analiz eden ve JSON formatında sunan API hizmeti.",
    supportedGames: "Desteklenen Oyunlar",
    dataView: "Veri Görünümü",
    latestPatch: "Son Güncel Yama",
    patchArchive: "Geçmiş Yamalar (Arşiv)",
    summaryLang: "Özet Dili",
    latestDataFor: "için Son Veri",
    archiveDataFor: "için Geçmiş Veri",
    archiveListLoading: "🔄 Arşiv listesi yükleniyor...",
    archiveSelectPrompt: "Lütfen bir arşiv tarihi seçin...",
    archiveNotFound: "Bu oyun için henüz bir arşiv kaydı bulunamadı.",
    patchLoading: "🔄 Yama verisi yükleniyor...",
    errorLoadingLatest: "Güncel veri çekilemedi:",
    errorLoadingList: "Arşiv listesi çekilemedi:",
    errorLoadingArchive: "Arşivlenmiş veri çekilemedi:",
    impactScore: "Yama Etki Skoru:",
    rawJson: "Ham JSON Çıktısı:",
    buffs: "🟢 Güçlendirmeler (Buffs)",
    nerfs: "🔴 Zayıflatmalar (Nerfs)",
    newContent: "✨ Yeni İçerik/Değişiklikler",
    fixes: "🔧 Hata Düzeltmeleri (Fixes)",
    other: "📋 Diğer Değişiklikler",
    noChanges:
      "ℹ️ Analiz tamamlandı ancak raporlanacak önemli değişiklik bulunamadı.",

    // --- Yeni eklenen çeviriler ---
    statistics: "📊 Kullanım İstatistikleri",
    statsLoading: "🔄 İstatistikler yükleniyor...",
    statsError: "İstatistikler çekilemedi:",
    totalRequests: "Toplam Analiz Edilen İstek:",
    totalErrors: "Toplam Hata:",
    mostPopular: "En Popüler Oyun:",
    requestsByGame: "Oyuna Göre İstek Sayıları:",
    noStats: "Henüz yeterli istatistik verisi yok.",
  },
  en: {
    headerTitle: "🎮 Game Patch Notes Intelligence API",
    headerSubtitle:
      "The API service that analyzes the latest game patches and serves them as JSON.",
    supportedGames: "Supported Games",
    dataView: "Data View",
    latestPatch: "Latest Patch",
    patchArchive: "Patch Archive (History)",
    summaryLang: "Summary Language",
    latestDataFor: "Latest Data for",
    archiveDataFor: "Archive Data for",
    archiveListLoading: "🔄 Loading archive list...",
    archiveSelectPrompt: "Please select an archive date...",
    archiveNotFound: "No archive records found for this game yet.",
    patchLoading: "🔄 Loading patch data...",
    errorLoadingLatest: "Failed to fetch latest data:",
    errorLoadingList: "Failed to fetch archive list:",
    errorLoadingArchive: "Failed to fetch archived data:",
    impactScore: "Patch Impact Score:",
    rawJson: "Raw JSON Output:",
    buffs: "🟢 Buffs",
    nerfs: "🔴 Nerfs",
    newContent: "✨ New Content/Changes",
    fixes: "🔧 Bug Fixes",
    other: "📋 Other Changes",
    noChanges:
      "ℹ️ Analysis complete, but no significant changes were found.",

    // --- New translations ---
    statistics: "📊 Usage Statistics",
    statsLoading: "🔄 Loading statistics...",
    statsError: "Failed to fetch statistics:",
    totalRequests: "Total Requests Analyzed:",
    totalErrors: "Total Errors:",
    mostPopular: "Most Popular Game:",
    requestsByGame: "Requests per Game:",
    noStats: "Not enough statistics data yet.",
  },
};

// --- API URL ---
// (API_URL'i bileşenlerin dışına, global bir alana taşıyoruz)
const API_URL = "https://game-patch-api.onrender.com";

// --- STİLLER ---
const GlobalStyles = () => (
  <style>{`
    :root {
      font-family: Inter, system-ui, Avenir, Helvetica, Arial, sans-serif;
      background-color: #242424;
      color: rgba(255, 255, 255, 0.87);
    }
    body { margin: 0; }
    .container { max-width: 900px; margin: 0 auto; padding: 2rem; }
    header { text-align: center; border-bottom: 1px solid #555; padding-bottom: 1rem; margin-bottom: 2rem; }
    h1 { color: #535bf2; }
    h2 { border-bottom: 1px solid #444; padding-bottom: 8px; }
    section { margin-top: 2rem; }
    .buttons { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 1rem; }
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
    .loading, .error { padding: 1rem; border-radius: 8px; margin-top: 1rem; }
    .loading { background-color: #333; }
    .error { background-color: #4b2525; color: #ffbaba; }
    .history-controls { margin-bottom: 1rem; }
    .history-select {
      width: 100%;
      padding: 10px 15px;
      border-radius: 8px;
      border: 1px solid #555;
      background-color: #1a1a1a;
      color: rgba(255, 255, 255, 0.87);
      font-size: 1em;
      font-family: inherit;
      cursor: pointer;
      transition: border-color 0.25s;
    }
    .history-select:hover, .history-select:focus {
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
    .impact-display span { margin-left: 10px; font-weight: bold; }
    .impact-küçük { background-color: #2a3a3a; border-color: #3fa8a8; color: #88f1f1; }
    .impact-orta { background-color: #4a4a2a; border-color: #a8a83f; color: #f1f188; }
    .impact-büyük { background-color: #4b2525; border-color: #a83f3f; color: #ffbaba; }
    .patch-changes-list { margin-top: 1.5rem; padding: 1rem; background-color: #1a1a1a; border-radius: 8px; }
    .patch-changes-list h3 { margin-top: 0.5rem; margin-bottom: 0.5rem; font-size: 1.2em; }
    .patch-changes-list ul { margin: 0; padding-left: 20px; }
    .patch-changes-list li { margin-bottom: 0.75rem; }
    .patch-changes-list strong { color: #a8a8ff; }
    .patch-changes-list .details { display: block; color: #ccc; margin-top: 2px; font-style: italic; }
    .change-group-buff h3 { color: #88f188; }
    .change-group-nerf h3 { color: #ffbaba; }
    .change-group-new h3 { color: #88d8f1; }
    .change-group-fix h3 { color: #f1f188; }
    .change-group-other h3 { color: #ccc; }
    .json-output { background-color: #1a1a1a; border-radius: 8px; padding: 1rem; overflow-x: auto; margin-top: 1rem; }
    pre { margin: 0; }

    /* --- İSTATİSTİK STİLLERİ --- */
    .stats-section {
      background-color: #1a1a1a;
      padding: 1.5rem;
      border-radius: 8px;
      margin-top: 2rem;
    }
    .stats-section ul { list-style: none; padding: 0; }
    .stats-section li {
      margin-bottom: 0.8rem;
      border-bottom: 1px solid #333;
      padding-bottom: 0.8rem;
    }
    .stats-section li:last-child { border-bottom: none; }
    .stats-section strong { color: #535bf2; margin-right: 10px; }
    .game-stats-list li {
      display: flex;
      justify-content: space-between;
      border: none;
      padding-bottom: 0.3rem;
      margin-bottom: 0.3rem;
      font-size: 0.9em;
    }
    .game-stats-list span:first-child { color: #ccc; }
    .game-stats-list span:last-child { font-weight: bold; }
  `}</style>
);

// --- BİLEŞENLER ---
const ImpactDisplay = ({ score, label, lang }) => {
  if (!score && score !== 0) return null;
  const t = i18n[lang];
  const impactClass = `impact-${label?.toLowerCase()}`;
  const emoji = label === "Büyük" ? "🔥" : label === "Orta" ? "⚠️" : "ℹ️";
  const translatedLabel =
    label === "Büyük"
      ? lang === "tr"
        ? "Büyük"
        : "High"
      : label === "Orta"
      ? lang === "tr"
        ? "Orta"
        : "Medium"
      : lang === "tr"
      ? "Küçük"
      : "Low";

  return (
    <div className={`impact-display ${impactClass}`}>
      <strong>
        {emoji} {t.impactScore}
      </strong>
      <span>
        {translatedLabel} ({score} / 10)
      </span>
    </div>
  );
};

const PatchNotesDisplay = ({ changes, lang }) => {
  const t = i18n[lang];
  if (!changes || changes.length === 0)
    return (
      <div className="patch-changes-list">
        <p>
          <i>{t.noChanges}</i>
        </p>
      </div>
    );

  const groups = { buff: [], nerf: [], new: [], fix: [], other: [] };
  changes.forEach((change) => {
    const type = change.type?.toLowerCase() || "other";
    if (groups[type]) groups[type].push(change);
    else groups.other.push(change);
  });

  const getDetailText = (details) => {
    if (typeof details === "object" && details !== null)
      return details[lang] || details.en || details.tr || "No details";
    return details || (lang === "tr" ? "Detay yok" : "No details available");
  };

  const titles = {
    buff: t.buffs,
    nerf: t.nerfs,
    new: t.newContent,
    fix: t.fixes,
    other: t.other,
  };

  return (
    <div className="patch-changes-list">
      {Object.entries(groups).map(
        ([type, list]) =>
          list.length > 0 && (
            <div key={type} className={`change-group change-group-${type}`}>
              <h3>{titles[type]}</h3>
              <ul>
                {list.map((c, i) => (
                  <li key={i}>
                    <strong>
                      {c.target}
                      {c.ability && ` (${c.ability})`}
                    </strong>
                    <span className="details">{getDetailText(c.details)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )
      )}
    </div>
  );
};

// --- YENİ: İSTATİSTİK BİLEŞENİ ---
const StatsDisplay = ({ lang }) => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const t = i18n[lang];

  useEffect(() => {
    const fetchStats = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await axios.get(`${API_URL}/public/stats`);
        setStats(response.data);
      } catch (err) {
        setError(`${t.statsError} ${err.response?.data?.detail || err.message}`);
      }
      setLoading(false);
    };
    fetchStats();
    const intervalId = setInterval(fetchStats, 5 * 60 * 1000);
    return () => clearInterval(intervalId);
  }, [t]);

  if (loading) return <div className="loading stats-section">{t.statsLoading}</div>;
  if (error) return <div className="error stats-section">❌ {error}</div>;
  if (!stats || stats.message)
    return <div className="loading stats-section">{stats?.message || t.noStats}</div>;

  const sortedGameStats = stats.requests_by_game
    ? Object.entries(stats.requests_by_game).sort(([, a], [, b]) => b - a)
    : [];

  return (
    <div className="stats-section">
      <h2>{t.statistics}</h2>
      <ul>
        <li>
          <strong>{t.totalRequests}</strong> {stats.total_requests_analyzed || 0}
        </li>
        <li>
          <strong>{t.totalErrors}</strong> {stats.total_errors || 0}
        </li>
        <li>
          <strong>{t.mostPopular}</strong> {stats.most_popular_game || "N/A"}
        </li>
        {sortedGameStats.length > 0 && (
          <li>
            <strong>{t.requestsByGame}</strong>
            <ul className="game-stats-list" style={{ marginTop: "0.5rem" }}>
              {sortedGameStats.map(([game, count]) => (
                <li key={game}>
                  <span>{game}:</span> <span>{count}</span>
                </li>
              ))}
            </ul>
          </li>
        )}
      </ul>
    </div>
  );
};

// --- ANA APP ---
const SUPPORTED_GAMES = [
  "Valorant",
  "Roblox",
  "Minecraft",
  "League of Legends",
  "Counter-Strike 2",
  "Fortnite",
];

function App() {
  const [mode, setMode] = useState("latest");
  const [selectedGame, setSelectedGame] = useState(SUPPORTED_GAMES[0]);
  const [patchData, setPatchData] = useState(null);
  const [archiveList, setArchiveList] = useState([]);
  const [selectedArchiveKey, setSelectedArchiveKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState(null);
  const [lang, setLang] = useState("en");
  const t = i18n[lang];

  const formatTimestamp = (isoString) => {
    try {
      const date = new Date(isoString);
      const locale = lang === "tr" ? "tr-TR" : "en-US";
      return date.toLocaleString(locale, {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  // --- PATCH VERİLERİ YÜKLEME ---
  useEffect(() => {
    setPatchData(null);
    setError(null);
    setArchiveList([]);
    setSelectedArchiveKey("");
    if (mode === "latest") {
      const load = async () => {
        setLoading(true);
        try {
          const res = await axios.get(`${API_URL}/public/patches`, {
            params: { game: selectedGame },
          });
          setPatchData(res.data);
        } catch (err) {
          setError(
            `${t.errorLoadingLatest} ${
              err.response?.data?.detail || err.message
            }`
          );
        }
        setLoading(false);
      };
      load();
    } else {
      // mode === "archive"
      const load = async () => {
        setLoadingHistory(true);
        try {
          const res = await axios.get(`${API_URL}/public/patches/history`, {
            params: { game: selectedGame },
          });
          setArchiveList(res.data.archives || []);
        } catch (err) {
          setError(
            `${t.errorLoadingList} ${err.response?.data?.detail || err.message}`
          );
        }
        setLoadingHistory(false);
      };
      load();
    }
  }, [selectedGame, mode, t]);

  // --- ARŞİV DETAY VERİSİ YÜKLEME ---
  useEffect(() => {
    // DÜZELTME: 'mode === "history"' yerine 'mode === "archive"' kullanılıyor
    if (selectedArchiveKey && mode === "archive") {
      const load = async () => {
        setLoading(true);
        setError(null);
        setPatchData(null);
        try {
          const res = await axios.get(`${API_URL}/public/patches/archive`, {
            params: { key: selectedArchiveKey },
          });
          // --- EKSİK KISIM EKLENDİ ---
          setPatchData(res.data);
        } catch (err) {
          setError(
            `${t.errorLoadingArchive} ${
              err.response?.data?.detail || err.message
            }`
          );
        }
        setLoading(false);
      };
      load();
    }
  }, [selectedArchiveKey, mode, t]);

  // --- YENİ: SSE Bağlantısı için useEffect ---
  useEffect(() => {
    console.log("Setting up EventSource...");
    const eventSource = new EventSource(`${API_URL}/events`);

    eventSource.onmessage = (event) => {
      try {
        const eventData = JSON.parse(event.data);
        console.log("SSE Event Received:", eventData);

        const normalizedSelectedGame = selectedGame
          .toLowerCase()
          .replace(" ", "_")
          .replace("-", "_")
          .replace(".", "");

        if (
          eventData.type === "new_patch" &&
          eventData.game === normalizedSelectedGame &&
          mode === "latest"
        ) {
          console.log(
            `New patch detected for ${selectedGame}, refreshing latest data...`
          );

          // Veriyi doğrudan yeniden yükle
          const loadLatestData = async () => {
            setLoading(true);
            setError(null);
            try {
              const res = await axios.get(`${API_URL}/public/patches`, {
                params: { game: selectedGame },
              });
              setPatchData(res.data);
              console.log("Latest data refreshed via SSE trigger.");
            } catch (err) {
              setError(
                `${t.errorLoadingLatest} ${
                  err.response?.data?.detail || err.message
                }`
              );
            }
            setLoading(false);
          };
          loadLatestData();
        }
      } catch (e) {
        console.error("Error parsing SSE event data:", e);
      }
    };

    eventSource.onerror = (error) => {
      console.error("EventSource failed:", error);
      eventSource.close();
    };

    return () => {
      console.log("Closing EventSource.");
      eventSource.close();
    };
  }, [selectedGame, mode, t]);

  return (
    <>
      <GlobalStyles />
      <div className="container">
        <header>
          <h1>{t.headerTitle}</h1>
          <p>{t.headerSubtitle}</p>
        </header>

        <main>
          <section>
            <h2>{t.supportedGames}</h2>
            <div className="buttons">
              {SUPPORTED_GAMES.map((game) => (
                <button
                  key={game}
                  className={selectedGame === game ? "active" : ""}
                  onClick={() => setSelectedGame(game)}
                >
                  {game}
                </button>
              ))}
            </div>
          </section>

          <section>
            <h2>{t.dataView}</h2>
            <div className="buttons">
              <button
                className={mode === "latest" ? "active" : ""}
                onClick={() => setMode("latest")}
              >
                {t.latestPatch}
              </button>
              <button
                className={mode === "archive" ? "active" : ""}
                onClick={() => setMode("archive")}
              >
                {t.patchArchive}
              </button>
            </div>
          </section>

          <section>
            <h2>{t.summaryLang}</h2>
            <div className="buttons">
              <button
                className={lang === "en" ? "active" : ""}
                onClick={() => setLang("en")}
              >
                English
              </button>
              <button
                className={lang === "tr" ? "active" : ""}
                onClick={() => setLang("tr")}
              >
                Türkçe
              </button>
            </div>
          </section>

          <section>
            <h2>
              {mode === "latest" ? t.latestDataFor : t.archiveDataFor}{" "}
              {selectedGame}
            </h2>

            {mode === "archive" && (
              <div className="history-controls">
                {loadingHistory && (
                  <div className="loading">{t.archiveListLoading}</div>
                )}
                {!loadingHistory && archiveList.length > 0 && (
                  <select
                    className="history-select"
                    value={selectedArchiveKey}
                    onChange={(e) => setSelectedArchiveKey(e.target.value)}
                  >
                    <option value="">{t.archiveSelectPrompt}</option>
                    {archiveList.map((archive) => (
                      <option key={archive.key} value={archive.key}>
                        {formatTimestamp(archive.date)} -{" "}
                        {archive.impact_label || "Bilgi Yok"} (
                        {archive.patch_version || "v?"})
                      </option>
                    ))}
                  </select>
                )}
                {!loadingHistory && archiveList.length === 0 && !error && (
                  <p>
                    <i>{t.archiveNotFound}</i>
                  </p>
                )}
              </div>
            )}

            {loading && <div className="loading">{t.patchLoading}</div>}
            {error && <div className="error">❌ {error}</div>}

            {patchData && (
              <>
                <ImpactDisplay
                  score={patchData.impact_score}
                  label={patchData.impact_label}
                  lang={lang}
                />
                <PatchNotesDisplay
                  changes={patchData.changes}
                  lang={lang}
                />

                <h3>{t.rawJson}</h3>
                <div className="json-output">
                  <pre>{JSON.stringify(patchData, null, 2)}</pre>
                </div>
              </>
            )}
          </section>

          {/* --- İSTATİSTİK BÖLÜMÜ --- */}
          <section>
            <StatsDisplay lang={lang} />
          </section>
        </main>
      </div>
    </>
  );
} // <-- EKSİK OLAN PARANTEZ BURADA

export default App;