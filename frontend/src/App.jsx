import { useState, useEffect } from 'react'
import axios from 'axios'
import './App.css' // Birazdan bunu da düzenleyeceğiz

// Render'daki backend API'nizin tam adresi.
// Render'daki "game-patch-api" servisinizin URL'si ile değiştirin.
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
  // State (Durum) Değişkenlerimiz
  const [selectedGame, setSelectedGame] = useState(SUPPORTED_GAMES[0]);
  const [patchData, setPatchData] = useState(null); // Gelen JSON verisi
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // 'selectedGame' her değiştiğinde bu fonksiyon yeniden çalışır
  useEffect(() => {
    // Veri çekme fonksiyonu
    const fetchPatches = async () => {
      setLoading(true);
      setError(null);
      setPatchData(null);
      try {
        const response = await axios.get(`${API_URL}/public/patches`, {
          params: { game: selectedGame }
        });
        // Gelen JSON verisini [cite: 247-268] state'e kaydediyoruz
        setPatchData(response.data); 
      } catch (err) {
        setError(`Veri çekilemedi: ${err.response?.data?.detail || err.message}`);
      }
      setLoading(false);
    };

    fetchPatches();
  }, [selectedGame]); // Bağımlılık: selectedGame

  return (
    <div className="container">
      <header>
        <h1>🎮 Game Patch Notes Intelligence API</h1>
        <p>En son oyun yamalarını analiz eden ve JSON formatında sunan API hizmeti.</p>
      </header>

      <main>
        {/* BÖLÜM 1: Desteklenen Oyunlar (İsteğiniz) */}
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

        {/* BÖLÜM 2: Son Yama Akışı ve JSON Çıktısı (İsteğiniz) */}
        <section className="patch-details">
          <h2>{selectedGame} için Son Veri</h2>
          
          {/* Yüklenme durumu */}
          {loading && <div className="loading">🔄 Yükleniyor...</div>}

          {/* Hata durumu */}
          {error && <div className="error">❌ {error}</div>}

          {/* Başarılı: JSON Verisini Göster (İsteğiniz) */}
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