"""Basit sözlük tabanlı TR/EN çeviri sistemi.

Qt'nin kendi tr()/.ts-.qm mekanizması yerine bunu seçtik: web paneli
(düz HTML/JS, bkz. webpanel/static/app.js — /api/strings) aynı anahtar
setini paylaşabilsin diye, ve PyInstaller build'ine (bkz. scripts/build.py)
ayrıca lupdate/lrelease adımı eklemeden.

Dil değişikliği ÇALIŞMA ANINDA mevcut pencereleri retranslate ETMEZ —
basitlik için kullanıcıya "değişiklik için yeniden başlat" denir (bkz.
gui/pages/settings.py). Masaüstü arayüzüne özgü metinler ayrı bir
dosyada (gui/strings.py) tutulur ve import edilince STRINGS'e eklenir. Her modül `from mcpack.i18n import t` ile
import edip t("anahtar") çağırır; dil `set_language()` ile uygulama
başlangıcında (main.py) Settings.language'tan bir kere ayarlanır.
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "tr"
SUPPORTED_LANGUAGES = ("tr", "en")

_current_language = DEFAULT_LANGUAGE

def set_language(lang: str) -> None:
    global _current_language
    _current_language = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

def get_language() -> str:
    return _current_language

# key -> {"tr": "...", "en": "..."}
# Dosya başına gruplar halinde (bkz. yorum satırları) — hangi string hangi
# GUI dosyasından geldiğini bulmak kolay olsun diye.
STRINGS: dict[str, dict[str, str]] = {
    # -- ortam etiketleri (gui/formatting.py) ---------------------------
    "env.client_server": {"tr": "İstemci + Sunucu", "en": "Client + Server"},
    "env.client": {"tr": "İstemci", "en": "Client"},
    "env.server": {"tr": "Sunucu", "en": "Server"},
    "env.unknown": {"tr": "Bilinmiyor", "en": "Unknown"},

    # -- server_runtime.py (GUI'de gösterilen hata/envanter etiketleri) -----
    "inventory.slot.boots": {"tr": "Zırh: Çizme", "en": "Armor: Boots"},
    "inventory.slot.leggings": {"tr": "Zırh: Pantolon", "en": "Armor: Leggings"},
    "inventory.slot.chestplate": {"tr": "Zırh: Göğüslük", "en": "Armor: Chestplate"},
    "inventory.slot.helmet": {"tr": "Zırh: Kask", "en": "Armor: Helmet"},
    "inventory.slot.offhand": {"tr": "İkinci El", "en": "Off Hand"},
    "inventory.slot.hotbar": {"tr": "Sıcak Çubuk", "en": "Hotbar"},
    "inventory.slot.main": {"tr": "Envanter", "en": "Inventory"},
    "runtime.error.server_file_download_failed": {
        "tr": (
            "Sunucu dosyası otomatik indirilemedi: {exc}. Minecraft "
            "{minecraft} / {loader} {loader_version} için resmi bir dosya "
            "bulunamamış olabilir."
        ),
        "en": (
            "Could not automatically download the server file: {exc}. There "
            "may be no official file for Minecraft {minecraft} / {loader} "
            "{loader_version}."
        ),
    },
    "runtime.error.install_failed": {
        "tr": "Kurulum başarısız oldu (çıkış kodu {returncode}):\n{tail}",
        "en": "Installation failed (exit code {returncode}):\n{tail}",
    },
    "runtime.error.not_runnable": {
        "tr": "Sunucu çalıştırılabilir değil — önce 'Hazırla' (ve gerekiyorsa 'Kur') yapın.",
        "en": "The server isn't runnable yet — run 'Prepare' (and 'Install' if needed) first.",
    },
    "cheat.error.file_changed": {
        "tr": "{name}: indirilen dosya, pack'e eklenirken kaydedilen dosyayla aynı değil (büyük ihtimalle yeni bir build yayınlandı). Güvenlik için pakete eklenmedi — Hile Modları bölümünden kaldırıp yeniden ekleyin.",
        "en": "{name}: the downloaded file doesn't match the one recorded when it was added (most likely a new build was published). It was not included for safety — remove it in Cheat Mods and add it again.",
    },
    "runtime.error.already_running": {"tr": "Sunucu zaten çalışıyor.", "en": "The server is already running."},
    "runtime.error.not_running_cant_send": {
        "tr": "Sunucu çalışmıyor, komut gönderilemedi.",
        "en": "The server isn't running, the command could not be sent.",
    },

    # -- server_properties.py (bkz. gui/pages/server_panel.py, webpanel/app.py) --
    "serverprop.motd.label": {"tr": "Sunucu Mesajı (MOTD)", "en": "Server Message (MOTD)"},
    "serverprop.difficulty.label": {"tr": "Zorluk", "en": "Difficulty"},
    "serverprop.gamemode.label": {"tr": "Oyun Modu", "en": "Game Mode"},
    "serverprop.max-players.label": {"tr": "Maks. Oyuncu", "en": "Max Players"},
    "serverprop.server-port.label": {"tr": "Port", "en": "Port"},
    "serverprop.pvp.label": {"tr": "PVP", "en": "PVP"},
    "serverprop.online-mode.label": {
        "tr": "Online Mode (Mojang hesap doğrulama)",
        "en": "Online Mode (Mojang account verification)",
    },
    "serverprop.white-list.label": {"tr": "Beyaz Liste", "en": "Whitelist"},
    "serverprop.level-seed.label": {
        "tr": "Dünya Tohumu (seed, sadece yeni dünyada etkili)",
        "en": "World Seed (only effective for a new world)",
    },
    "serverprop.view-distance.label": {"tr": "Görüş Mesafesi (chunk)", "en": "View Distance (chunks)"},

    # -- webpanel/app.py (backend hata mesajları) ------------------------------
    "webpanel.error.pack_not_found": {"tr": "Pack bulunamadı.", "en": "Pack not found."},
    "webpanel.error.server_not_running": {"tr": "Sunucu çalışmıyor.", "en": "Server is not running."},
    "webpanel.error.login_required": {"tr": "Giriş gerekli.", "en": "Login required."},
    "webpanel.error.wrong_password": {"tr": "Şifre yanlış.", "en": "Wrong password."},
    "webpanel.error.installer_not_found": {
        "tr": "Kurulum dosyası bulunamadı — önce Hazırla.",
        "en": "Installer file not found — run Prepare first.",
    },
    "webpanel.error.java_not_found": {
        "tr": "Java bulunamadı. Ayarlar'dan Java yolunu belirtin.",
        "en": "Java not found. Set the Java path in Settings.",
    },
    "webpanel.error.eula_required": {
        "tr": "EULA kabul edilmeden sunucu başlatılamaz.",
        "en": "The server cannot be started without accepting the EULA.",
    },
    "webpanel.error.server_already_running": {"tr": "Sunucu zaten çalışıyor.", "en": "Server is already running."},
    "webpanel.error.server_not_ready": {
        "tr": "Sunucu hazır değil — önce Hazırla (ve gerekiyorsa Kur).",
        "en": "Server is not ready — run Prepare first (and Install if needed).",
    },
    "webpanel.error.timeout": {
        "tr": "Sunucudan yanıt alınamadı (zaman aşımı).",
        "en": "No response from the server (timed out).",
    },
    "webpanel.error.server_not_found_ws": {"tr": "Sunucu bulunamadı.", "en": "Server not found."},
    "webpanel.error.invalid_player": {
        "tr": "Geçersiz oyuncu adı (sadece harf, rakam ve _; en fazla 16 karakter).",
        "en": "Invalid player name (letters, digits and _ only; max 16 characters).",
    },
    "webpanel.error.too_many_attempts": {
        "tr": "Çok fazla hatalı giriş denemesi. Birkaç dakika sonra tekrar deneyin.",
        "en": "Too many failed login attempts. Try again in a few minutes.",
    },
    "webpanel.error.no_free_port": {
        "tr": "Web paneli için {host} üzerinde {start}–{end} aralığında boş port bulunamadı. Ayarlar'dan farklı bir port seçin.",
        "en": "No free port in {start}–{end} on {host} for the web panel. Pick a different port in Settings.",
    },
    "webpanel.error.start_failed": {
        "tr": "Web paneli {host}:{port} üzerinde başlatılamadı — port başka bir program tarafından kullanılıyor olabilir. Ayarlar'dan farklı bir port seçin.",
        "en": "Could not start the web panel on {host}:{port} — the port may be in use by another program. Pick a different port in Settings.",
    },

    # -- webpanel/static/index.html + app.js (frontend) --------------------------
    "webpanel.app_title": {"tr": "🖥 mcpack Web Paneli", "en": "🖥 mcpack Web Panel"},
    "webpanel.login.subtitle": {
        "tr": "Bu panel ağdaki diğer cihazlardan da erişilebilir — şifrenizi girin.",
        "en": "This panel can also be reached from other devices on the network — enter your password.",
    },
    "webpanel.login.password_placeholder": {"tr": "Şifre", "en": "Password"},
    "webpanel.login.submit": {"tr": "Giriş Yap", "en": "Log In"},
    "webpanel.empty_state": {"tr": "Soldan bir pack seçin.", "en": "Select a pack on the left."},
    "webpanel.status.stopped": {"tr": "Durduruldu", "en": "Stopped"},
    "webpanel.status.running": {"tr": "Çalışıyor", "en": "Running"},
    "webpanel.btn.prepare": {"tr": "Hazırla / Güncelle", "en": "Prepare / Update"},
    "webpanel.btn.install": {"tr": "Kur (installServer)", "en": "Install (installServer)"},
    "webpanel.btn.start": {"tr": "Başlat", "en": "Start"},
    "webpanel.btn.stop": {"tr": "Durdur", "en": "Stop"},
    "webpanel.mods_bar.title": {
        "tr": "Modlar (sunucuda çalışacak): {count}",
        "en": "Mods (will run on the server): {count}",
    },
    "webpanel.mods_bar.excluded": {
        "tr": "+ {count} istemci-only mod sunucu için hariç tutuldu.",
        "en": "+ {count} client-only mod excluded for the server.",
    },
    "webpanel.tab.console": {"tr": "Konsol", "en": "Console"},
    "webpanel.tab.players": {"tr": "Oyuncular", "en": "Players"},
    "webpanel.tab.settings": {"tr": "Ayarlar", "en": "Settings"},
    "webpanel.btn.clear_console": {"tr": "Konsolu Temizle", "en": "Clear Console"},
    "webpanel.label.auto_scroll": {"tr": "Otomatik Kaydır", "en": "Auto-Scroll"},
    "webpanel.command_placeholder": {
        "tr": "Sunucu komutu yazın (ör. say merhaba, op <isim>) — ↑/↓ ile geçmiş...",
        "en": "Type a server command (e.g. say hello, op <name>) — ↑/↓ for history...",
    },
    "webpanel.btn.send": {"tr": "Gönder", "en": "Send"},
    "webpanel.players.online_title": {"tr": "Çevrimiçi Oyuncular", "en": "Online Players"},
    "webpanel.btn.refresh_players": {"tr": "Listeyi Yenile", "en": "Refresh List"},
    "webpanel.players.select_prompt": {"tr": "Bir oyuncu seçin.", "en": "Select a player."},
    "webpanel.players.running_required": {
        "tr": "Oyuncu paneli için sunucu çalışıyor olmalı.",
        "en": "The server must be running for the player panel.",
    },
    "webpanel.players.none_online": {"tr": "Çevrimiçi oyuncu yok.", "en": "No players online."},
    "webpanel.btn.heal": {"tr": "İyileştir", "en": "Heal"},
    "webpanel.btn.kill": {"tr": "Öldür", "en": "Kill"},
    "webpanel.btn.feed": {"tr": "Doyur", "en": "Feed"},
    "webpanel.btn.damage": {"tr": "Hasar Ver", "en": "Damage"},
    "webpanel.hunger.tooltip": {
        "tr": (
            "Vanilla'da açlığı anında belirli bir değere ayarlamanın bir yolu yok — "
            "bu, süre boyunca normalden daha hızlı acıktırır."
        ),
        "en": (
            "There is no way to set hunger to an exact value instantly in vanilla — "
            "this makes the player hungrier faster than normal for the duration."
        ),
    },
    "webpanel.btn.hunger": {"tr": "Açlığı Azalt", "en": "Reduce Hunger"},
    "webpanel.inventory.title": {
        "tr": "Envanter (zırh + ikinci el dahil) — salt okunur",
        "en": "Inventory (including armor + offhand) — read-only",
    },
    "webpanel.btn.view_inventory": {"tr": "Envanteri Görüntüle", "en": "View Inventory"},
    "webpanel.table.section": {"tr": "Bölüm", "en": "Section"},
    "webpanel.table.item": {"tr": "Eşya", "en": "Item"},
    "webpanel.table.count": {"tr": "Adet", "en": "Count"},
    "webpanel.table.slot": {"tr": "Slot", "en": "Slot"},
    "webpanel.ender.title": {"tr": "Ender Sandığı — salt okunur", "en": "Ender Chest — read-only"},
    "webpanel.btn.view_ender": {"tr": "Ender Sandığını Görüntüle", "en": "View Ender Chest"},
    "webpanel.settings.runtime_title": {"tr": "Çalışma Ayarları", "en": "Runtime Settings"},
    "webpanel.settings.memory_label": {"tr": "Bellek (RAM)", "en": "Memory (RAM)"},
    "webpanel.settings.world_label": {"tr": "Dünya", "en": "World"},
    "webpanel.world.none": {"tr": "(dünya yok)", "en": "(no world)"},
    "webpanel.settings.performance_label": {"tr": "Performans", "en": "Performance"},
    "webpanel.settings.optimized_flags_label": {
        "tr": "Performans bayraklarını kullan (Aikar's flags)",
        "en": "Use performance flags (Aikar's flags)",
    },
    "webpanel.btn.save_settings": {"tr": "Ayarları Kaydet", "en": "Save Settings"},
    "webpanel.btn.save_properties": {
        "tr": "server.properties'i Kaydet",
        "en": "Save server.properties",
    },
    "webpanel.memory.custom": {"tr": "Özel (MB)", "en": "Custom (MB)"},
    "webpanel.memory.unknown": {
        "tr": "Sistem RAM'i tespit edilemedi — üst sınır konmadı, dikkatli seçin.",
        "en": "System RAM could not be detected — no upper limit set, choose carefully.",
    },
    "webpanel.memory.info": {
        "tr": (
            "Sisteminizde toplam ~{total_gb} GB RAM var. Sunucuya en fazla ~{max_gb} GB "
            "ayrılabiliyor (en az 2 GB size bırakılıyor)."
        ),
        "en": (
            "Your system has ~{total_gb} GB RAM in total. At most ~{max_gb} GB can be "
            "allocated to the server (at least 2 GB is left for you)."
        ),
    },
    "webpanel.badge.network_exposed": {"tr": "🌐 Ağa Açık", "en": "🌐 Open to Network"},
    "webpanel.badge.local_only": {"tr": "🔒 Sadece Bu Bilgisayar", "en": "🔒 This Computer Only"},
    "webpanel.servers.none": {"tr": "Hiç pack yok.", "en": "No packs yet."},
    "webpanel.toast.preparing": {
        "tr": "Hazırlanıyor (mod + sunucu dosyası indiriliyor)...",
        "en": "Preparing (downloading mods + server file)...",
    },
    "webpanel.toast.prepared": {"tr": "Hazırlandı.", "en": "Prepared."},
    "webpanel.toast.installing": {
        "tr": "Kuruluyor (java -jar ... --installServer)... bu biraz sürebilir.",
        "en": "Installing (java -jar ... --installServer)... this may take a while.",
    },
    "webpanel.toast.installed": {"tr": "Kurulum tamamlandı.", "en": "Installation complete."},
    "webpanel.eula.confirm": {
        "tr": (
            "Yerel bir sunucu çalıştırmak için Mojang'ın Minecraft EULA'sını kabul "
            "etmeniz gerekir:\n\nhttps://www.minecraft.net/eula\n\nKabul ediyor musunuz?"
        ),
        "en": (
            "To run a local server you must accept Mojang's Minecraft EULA:\n\n"
            "https://www.minecraft.net/eula\n\nDo you accept?"
        ),
    },
    "webpanel.toast.starting": {"tr": "Sunucu başlatılıyor...", "en": "Starting server..."},
    "webpanel.toast.stopping": {
        "tr": "Sunucu durduruluyor (stop komutu gönderildi)...",
        "en": "Stopping server (stop command sent)...",
    },
    "webpanel.console.process_exited": {"tr": "Sunucu süreci kapandı.", "en": "Server process exited."},
    "webpanel.toast.settings_saved": {"tr": "Ayarlar kaydedildi.", "en": "Settings saved."},
    "webpanel.toast.properties_saved": {"tr": "server.properties kaydedildi.", "en": "server.properties saved."},
    "webpanel.toast.player_action_sent": {"tr": "{player}: {action} gönderildi.", "en": "{player}: {action} sent."},
    # -- webpanel/static v2 (yeni arayüz) ----------------------------------------
    "webpanel.tab.properties": {"tr": "server.properties", "en": "server.properties"},
    "webpanel.tab.logs": {"tr": "Uygulama Logları", "en": "App Logs"},
    "webpanel.tab.diagnostics": {"tr": "Teşhis", "en": "Diagnostics"},
    "webpanel.search_servers": {"tr": "Pack ara…", "en": "Search packs…"},
    "webpanel.btn.logout": {"tr": "Çıkış", "en": "Log out"},
    "webpanel.btn.copy": {"tr": "Kopyala", "en": "Copy"},
    "webpanel.btn.download": {"tr": "İndir", "en": "Download"},
    "webpanel.btn.op": {"tr": "OP yap", "en": "Op"},
    "webpanel.btn.deop": {"tr": "OP'yi al", "en": "Deop"},
    "webpanel.btn.kick": {"tr": "At", "en": "Kick"},
    "webpanel.state.not_prepared": {"tr": "Hazırlanmadı", "en": "Not prepared"},
    "webpanel.state.needs_install": {"tr": "Kurulum bekliyor", "en": "Needs install"},
    "webpanel.state.ready": {"tr": "Hazır", "en": "Ready"},
    "webpanel.console.filter_all": {"tr": "Tüm satırlar", "en": "All lines"},
    "webpanel.console.filter_warn": {"tr": "Uyarı +", "en": "Warnings +"},
    "webpanel.console.filter_error": {"tr": "Sadece hata", "en": "Errors only"},
    "webpanel.console.find": {"tr": "Konsolda ara…", "en": "Find in console…"},
    "webpanel.console.quick": {"tr": "Hızlı:", "en": "Quick:"},
    "webpanel.console.lines": {"tr": "{count} satır", "en": "{count} lines"},
    "webpanel.console.copied": {"tr": "Konsol panoya kopyalandı.", "en": "Console copied to clipboard."},
    "webpanel.connection.live": {"tr": "Canlı", "en": "Live"},
    "webpanel.connection.lost": {"tr": "Bağlantı koptu — yeniden bağlanılıyor…", "en": "Connection lost — reconnecting…"},
    "webpanel.confirm.kill": {"tr": "{player} öldürülsün mü?", "en": "Kill {player}?"},
    "webpanel.confirm.stop": {"tr": "Sunucu durdurulsun mu? (dünya kaydedilir)", "en": "Stop the server? (the world is saved)"},
    "webpanel.logs.level": {"tr": "Seviye", "en": "Level"},
    "webpanel.logs.search": {"tr": "Loglarda ara…", "en": "Search logs…"},
    "webpanel.logs.pause": {"tr": "Duraklat", "en": "Pause"},
    "webpanel.logs.resume": {"tr": "Devam", "en": "Resume"},
    "webpanel.logs.empty": {"tr": "Gösterilecek log yok.", "en": "No logs to show."},
    "webpanel.diag.system": {"tr": "Sistem", "en": "System"},
    "webpanel.diag.network": {"tr": "Ağ istekleri", "en": "Network requests"},
    "webpanel.diag.exceptions": {"tr": "Son istisnalar", "en": "Recent exceptions"},
    "webpanel.diag.none": {"tr": "İstisna yok.", "en": "No exceptions."},
    "webpanel.diag.stats": {
        "tr": "{total} istek · {failed} başarısız · ort. {avg} ms",
        "en": "{total} requests · {failed} failed · avg {avg} ms",
    },
    "webpanel.diag.refresh": {"tr": "Yenile", "en": "Refresh"},
    "webpanel.menu": {"tr": "Menü", "en": "Menu"},
}

def t(key: str, **kwargs: object) -> str:
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(_current_language) or entry.get(DEFAULT_LANGUAGE) or key
    return text.format(**kwargs) if kwargs else text

def strings_with_prefix(prefix: str) -> dict[str, str]:
    """webpanel/app.py:/api/strings için — Python tarafındaki STRINGS'in bir
    alt kümesini (anahtar -> o anki dildeki çeviri) JSON olarak frontend'e
    verir; webpanel/static/app.js kendi ayrı bir çeviri tablosu TUTMAZ, aynı
    STRINGS sözlüğünü (bkz. modül docstring'i) bu uç noktadan paylaşır."""
    return {key: t(key) for key in STRINGS if key.startswith(prefix)}
