import { useState, useEffect } from 'react'
import axios from 'axios'
import './App.css' // Stil dosyamızı import ediyoruz

// Render'daki backend API'nizin tam adresi
const API_URL = "https://game-patch-api.onrender.com";

// sources.yaml dosyanızdaki "game" isimleri
const SUPPORTED_GAMES = [
  "Valorant",
  "Roblox",
  "Minecraft",
  "League of Legends",
  "Counter-Strike 2",
  "Fortnite"
];

function App() {
  // --- State (Durum) Değişkenlerimiz ---

  // Sekme yönetimi: 'latest' (Güncel) veya 'history' (Geçmiş) [cite: 1.1]
  const [mode, setMode] = useState('latest'); 
  const [selectedGame, setSelectedGame] = useState(SUPPORTED_GAMES[0]);
  
  // Veri State'leri
  const [patchData, setPatchData] = useState(null); // Gelen JSON verisi
  const [archiveList, setArchiveList] = useState([]); // Tarih seçici için arşiv listesi [cite: 1.1]
  const [selectedArchiveKey, setSelectedArchiveKey] = useState(""); // Seçilen arşivin S3 anahtarı

  // Arayüz (UI) State'leri
  const [loading, setLoading] = useState(false); // Ana JSON alanı için yüklenme durumu
  const [loadingHistory, setLoadingHistory] = useState(false); // Arşiv listesi (dropdown) için yüklenme durumu
  const [error, setError] = useState(null);

  /**
   * ISO formatındaki tarihi (örn: 2025-10-25T17:30:45Z)
   * TR formatına (örn: 25.10.2025 20:30:45) çevirir.
   */
  const formatTimestamp = (isoString) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString('tr-TR', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      });
    } catch (e) {
      return isoString; // Hata olursa orijinal metni döndür
    }
  }

  // --- Logic Hooks (Mantık Akışları) ---

  // HOOK 1 & 2: Kullanıcı OYUN veya MOD (Sekme) değiştirdiğinde çalışır.
  // Ya 'Güncel Yama'yı ya da 'Geçmiş Yama Listesi'ni çeker.
  useEffect(() => {
    // Her değişiklikte önce ekranı temizle
    setPatchData(null);
    setError(null);
    setArchiveList([]);
    setSelectedArchiveKey("");

    if (mode === 'latest') {
      // --- MOD 1: GÜNCEL YAMA ---
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
      // --- MOD 2: GEÇMİŞ YAMA LİSTESİ (Dropdown için) ---
      const fetchHistoryList = async () => {
        setLoadingHistory(true); // Dropdown için ayrı yüklenme durumu
        try {
          const response = await axios.get(`${API_URL}/public/patches/history`, {
            params: { game: selectedGame }
          });
          setArchiveList(response.data.archives || []);
        } catch (err) {
          // Ana hatayı kirletme, sadece dropdown bölgesinde göster
          setError(`Arşiv listesi çekilemedi: ${err.response?.data?.detail || err.message}`);
        }
        setLoadingHistory(false);
      };
      fetchHistoryList();
    }
  }, [selectedGame, mode]); // selectedGame veya mode her değiştiğinde bu hook tetiklenir

  // HOOK 3: Kullanıcı 'Tarih Seçici' dropdown'ından bir seçim yaptığında çalışır.
  useEffect(() => {
    // Sadece bir arşiv anahtarı seçilmişse ve mod 'history' ise çalış
    if (selectedArchiveKey && mode === 'history') {
      const fetchArchivedPatch = async () => {
        setLoading(true); // Ana JSON alanı için yüklenme durumu
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
  }, [selectedArchiveKey]); // Sadece selectedArchiveKey değiştiğinde tetiklenir

  // --- JSX (Görsel Arayüz) ---
  return (
    <div className="container">
      <header>
        <h1>🎮 Game Patch Notes Intelligence API</h1>
        <p>En son oyun yamalarını analiz eden ve JSON formatında sunan API hizmeti.</p>
      </header>

      <main>
        {/* BÖLÜM 1: Desteklenen Oyunlar (Değişiklik yok) */}
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

        {/* BÖLÜM 2: YENİ SEKMELER (Güncel / Geçmiş) [cite: 1.1] */}
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

        {/* BÖLÜM 3: GÜNCELLENMİŞ YAMA DETAYLARI ALANI */}
        <section className="patch-details">
          <h2>
            {selectedGame} için 
            {mode === 'latest' ? ' Son Veri' : ' Geçmiş Veri'}
          </h2>
          
          {/* YENİ: Tarih Seçici (Sadece 'history' modunda görünür) [cite: 1.1] */}
          {mode === 'history' && (
            <div className="history-controls">
              {loadingHistory && <div className="loading">🔄 Arşiv listesi yükleniyor...</div>}
              
              {!loadingHistory && archiveList.length > 0 && (
                <select 
                  className="history-select" // CSS'te buna stil verdik
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

          {/* Ana Veri Gösterim Alanı (Her iki mod için ortak) */}

          {/* Yüklenme durumu */}
          {loading && <div className="loading">🔄 Yama verisi yükleniyor...</div>}

          {/* Hata durumu */}
          {error && <div className="error">❌ {error}</div>}

          {/* Başarılı: JSON Verisini Göster */}
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
  )
}

export default App

