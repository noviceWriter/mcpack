"""Basit sözlük tabanlı TR/EN çeviri sistemi.

Qt'nin kendi tr()/.ts-.qm mekanizması yerine bunu seçtik: web paneli
(düz HTML/JS, bkz. webpanel/static/i18n.js) aynı anahtar setini
paylaşabilsin diye, ve PyInstaller build'ine (bkz. scripts/build.py)
ayrıca lupdate/lrelease adımı eklemeden.

Dil değişikliği ÇALIŞMA ANINDA mevcut pencereleri retranslate ETMEZ —
basitlik için kullanıcıya "değişiklik için yeniden başlat" denir (bkz.
gui/settings_dialog.py). Her modül `from mcpack.i18n import t` ile
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
    # -- widgets.py -----------------------------------------------------
    "env.client_server": {"tr": "İstemci + Sunucu", "en": "Client + Server"},
    "env.client": {"tr": "İstemci", "en": "Client"},
    "env.server": {"tr": "Sunucu", "en": "Server"},
    "env.unknown": {"tr": "Bilinmiyor", "en": "Unknown"},
    "mod.already_in_pack": {"tr": "✓ Pack'te", "en": "✓ In Pack"},
    "search.default_title": {"tr": "Mod Ara", "en": "Search Mods"},
    "search.query_placeholder": {"tr": "Mod adı...", "en": "Mod name..."},
    "search.add_button": {"tr": "Seçili Modu Pack'e Ekle", "en": "Add Selected Mod to Pack"},
    "search.source_all": {"tr": "Tümü (Modrinth + CurseForge)", "en": "All (Modrinth + CurseForge)"},
    "search.view_flat": {"tr": "Toplu Liste", "en": "Flat List"},
    "search.view_category": {"tr": "Kategoriye Göre", "en": "By Category"},
    "search.button": {"tr": "Ara", "en": "Search"},
    "search.other_category": {"tr": "Diğer", "en": "Other"},

    # -- settings_dialog.py ----------------------------------------------
    "settings.title": {"tr": "Ayarlar", "en": "Settings"},
    "settings.section.language": {"tr": "Dil", "en": "Language"},
    "settings.language.tr": {"tr": "Türkçe", "en": "Turkish"},
    "settings.language.en": {"tr": "İngilizce", "en": "English"},
    "settings.language.label": {"tr": "Arayüz dili:", "en": "Interface language:"},
    "settings.language.restart_note": {
        "tr": "Dil değişikliği uygulamayı yeniden başlatınca etkili olur.",
        "en": "The language change takes effect after restarting the app.",
    },
    "settings.section.mod_sources": {"tr": "Mod Kaynakları", "en": "Mod Sources"},
    "settings.cf_test_button": {"tr": "Bağlantıyı Test Et", "en": "Test Connection"},
    "settings.cf_api_key_label": {"tr": "CurseForge API Key:", "en": "CurseForge API Key:"},
    "settings.prefer_modrinth": {
        "tr": "Aynı mod iki kaynakta da varsa Modrinth'i tercih et",
        "en": "Prefer Modrinth when a mod exists on both sources",
    },
    "settings.section.sklauncher": {"tr": "SKLauncher", "en": "SKLauncher"},
    "settings.browse_button": {"tr": "Gözat...", "en": "Browse..."},
    "settings.sklauncher_path_label": {"tr": "Taşınabilir Yol:", "en": "Portable Path:"},
    "settings.section.local_server": {"tr": "Yerel Sunucu", "en": "Local Server"},
    "settings.java_placeholder": {
        "tr": "Boşsa PATH'teki java kullanılır",
        "en": "If empty, uses java from PATH",
    },
    "settings.java_path_label": {"tr": "Java Yolu:", "en": "Java Path:"},
    "settings.section.web_panel": {"tr": "Web Paneli", "en": "Web Panel"},
    "settings.web_panel_port_label": {"tr": "Port:", "en": "Port:"},
    "settings.web_panel_password_placeholder": {
        "tr": "Boşsa panel ağa AÇILMAZ, sadece bu bilgisayardan erişilir",
        "en": "If empty, the panel is NOT exposed to the network, only this computer",
    },
    "settings.web_panel_password_label": {"tr": "Şifre:", "en": "Password:"},
    "settings.web_panel_note": {
        "tr": (
            "Şifre girerseniz panel aynı ağdaki (ör. telefonunuz) diğer cihazlardan da "
            "erişilebilir olur — bu yüzden şifre ZORUNLUDUR. Boş bırakırsanız panel sadece "
            "bu bilgisayardan açılabilir."
        ),
        "en": (
            "If you set a password, the panel becomes reachable from other devices on the "
            "same network (e.g. your phone) — a password is therefore REQUIRED for that. "
            "Leaving it empty keeps the panel reachable only from this computer."
        ),
    },
    "settings.section.export": {"tr": "Dışa Aktarma", "en": "Export"},
    "settings.exclude_logs": {
        "tr": "Dışa aktarımda logs/ klasörünü hariç tut",
        "en": "Exclude the logs/ folder from export",
    },
    "settings.exclude_crash_reports": {
        "tr": "Dışa aktarımda crash-reports/ klasörünü hariç tut",
        "en": "Exclude the crash-reports/ folder from export",
    },
    "settings.exclude_saves": {
        "tr": "Dışa aktarımda saves/ klasörünü hariç tut",
        "en": "Exclude the saves/ folder from export",
    },
    "settings.sklauncher_dialog_title": {
        "tr": "Taşınabilir SKLauncher Seç",
        "en": "Select Portable SKLauncher",
    },
    "settings.java_dialog_title": {
        "tr": "Java Yürütülebilir Dosyasını Seç",
        "en": "Select Java Executable",
    },
    "settings.cf_checking": {"tr": "Kontrol ediliyor...", "en": "Checking..."},
    "settings.cf_connected": {"tr": "✓ Bağlandı ({game_name})", "en": "✓ Connected ({game_name})"},
    "settings.cf_connection_failed": {
        "tr": "✗ Bağlanamadı: {message}",
        "en": "✗ Could not connect: {message}",
    },

    # -- common (paylaşılan kısa etiketler) -------------------------------
    "common.loading": {"tr": "Yükleniyor...", "en": "Loading..."},
    "common.not_found": {"tr": "Bulunamadı", "en": "Not found"},

    # -- new_pack_dialog.py -----------------------------------------------
    "newpack.loader_vanilla": {"tr": "Vanilla (loader yok)", "en": "Vanilla (no loader)"},
    "newpack.title": {"tr": "Yeni Pack", "en": "New Pack"},
    "newpack.name_label": {"tr": "İsim:", "en": "Name:"},
    "newpack.loader_version_label": {"tr": "Loader Versiyonu:", "en": "Loader Version:"},
    "newpack.author_label": {"tr": "Yazar:", "en": "Author:"},
    "newpack.summary_label": {"tr": "Açıklama:", "en": "Description:"},
    "newpack.mc_versions_load_failed_item": {
        "tr": "Yüklenemedi (elle giremezsiniz, tekrar deneyin)",
        "en": "Failed to load (manual entry not possible, try again)",
    },
    "newpack.mc_versions_load_failed": {
        "tr": "Minecraft versiyon listesi yüklenemedi: {message}",
        "en": "Failed to load Minecraft version list: {message}",
    },
    "newpack.loader_versions_not_found": {
        "tr": "{mc_version} için {loader} versiyonu bulunamadı.",
        "en": "No {loader} version found for {mc_version}.",
    },
    "newpack.loader_version_latest": {"tr": "{version}  (en yeni)", "en": "{version}  (latest)"},
    "newpack.load_failed_item": {"tr": "Yüklenemedi", "en": "Failed to load"},
    "newpack.recommended_suffix": {"tr": "⭐ Önerilen", "en": "⭐ Recommended"},
    "newpack.error_name_empty": {"tr": "İsim boş olamaz.", "en": "Name cannot be empty."},
    "newpack.error_select_mc_version": {
        "tr": "Minecraft versiyonu seçin.",
        "en": "Select a Minecraft version.",
    },
    "newpack.error_select_loader_version": {
        "tr": "Loader versiyonu seçin.",
        "en": "Select a loader version.",
    },

    # -- fork_pack_dialog.py ------------------------------------------------
    "forkpack.title": {"tr": "Başka Sürüme Uyarla (Fork)", "en": "Adapt to Another Version (Fork)"},
    "forkpack.name_default": {"tr": "{name} (Fork)", "en": "{name} (Fork)"},
    "forkpack.info": {
        "tr": (
            "'{name}' pack'indeki her mod, seçtiğiniz yeni Minecraft versiyonu "
            "için tekrar aranır. Uygun bir versiyonu bulunamayan modlar yeni "
            "pack'e eklenmez — işlem bitince hangilerinin atlandığı gösterilir."
        ),
        "en": (
            "Every mod in the '{name}' pack is re-searched for the new "
            "Minecraft version you pick. Mods without a matching version are "
            "not added to the new pack — you'll see which ones were skipped "
            "when it's done."
        ),
    },
    "forkpack.new_name_label": {"tr": "Yeni Pack Adı:", "en": "New Pack Name:"},
    "forkpack.new_mc_version_label": {
        "tr": "Yeni Minecraft Versiyonu:",
        "en": "New Minecraft Version:",
    },
    "forkpack.current_version_suffix": {"tr": "{version}  (mevcut versiyon)", "en": "{version}  (current version)"},
    "forkpack.mc_versions_load_failed_item": {
        "tr": "Yüklenemedi (tekrar deneyin)",
        "en": "Failed to load (try again)",
    },

    # -- mod_search_dialog.py ------------------------------------------------
    "modsearch.title_content": {"tr": "İçerik Ekle", "en": "Add Content"},
    "modsearch.title_mod": {"tr": "Mod Ekle", "en": "Add Mod"},
    "modsearch.menu_mods": {"tr": "Modlar", "en": "Mods"},
    "modsearch.menu_world": {"tr": "Dünya", "en": "World"},
    "modsearch.world_search_title": {"tr": "Dünya Ara (CurseForge)", "en": "Search Worlds (CurseForge)"},
    "modsearch.world_placeholder": {"tr": "Dünya/harita adı...", "en": "World/map name..."},
    "modsearch.world_add_button": {
        "tr": "Seçili dünyayı indir ve pack'e ekle",
        "en": "Download selected world and add to pack",
    },
    "modsearch.world_installed_label": {"tr": "Yüklü dünyalar:", "en": "Installed worlds:"},
    "modsearch.world_remove_button": {"tr": "Seçili dünyayı kaldır", "en": "Remove selected world"},

    "content.shader.label": {"tr": "Shader", "en": "Shader"},
    "content.shader.search_title": {"tr": "Shader Ara", "en": "Search Shaders"},
    "content.shader.placeholder": {"tr": "Shader adı...", "en": "Shader name..."},
    "content.shader.add_button": {
        "tr": "Seçili Shader'i Pack'e Ekle",
        "en": "Add Selected Shader to Pack",
    },
    "content.shader.installed_label": {"tr": "Eklenmiş shaderler:", "en": "Installed shaders:"},
    "content.shader.remove_button": {"tr": "Seçili shaderi kaldır", "en": "Remove selected shader"},

    "content.datapack.label": {"tr": "Datapack", "en": "Datapack"},
    "content.datapack.search_title": {"tr": "Datapack Ara", "en": "Search Datapacks"},
    "content.datapack.placeholder": {"tr": "Datapack adı...", "en": "Datapack name..."},
    "content.datapack.add_button": {
        "tr": "Seçili Datapack'i Pack'e Ekle",
        "en": "Add Selected Datapack to Pack",
    },
    "content.datapack.installed_label": {"tr": "Eklenmiş datapackler:", "en": "Installed datapacks:"},
    "content.datapack.remove_button": {"tr": "Seçili datapacki kaldır", "en": "Remove selected datapack"},

    "content.resourcepack.label": {"tr": "Görüntü paketi", "en": "Resource Pack"},
    "content.resourcepack.search_title": {"tr": "Görüntü Paketi Ara", "en": "Search Resource Packs"},
    "content.resourcepack.placeholder": {
        "tr": "Görüntü paketi adı...",
        "en": "Resource pack name...",
    },
    "content.resourcepack.add_button": {
        "tr": "Seçili Görüntü Paketini Pack'e Ekle",
        "en": "Add Selected Resource Pack to Pack",
    },
    "content.resourcepack.installed_label": {
        "tr": "Eklenmiş görüntü paketleri:",
        "en": "Installed resource packs:",
    },
    "content.resourcepack.remove_button": {
        "tr": "Seçili görüntü paketini kaldır",
        "en": "Remove selected resource pack",
    },

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
    "runtime.error.already_running": {"tr": "Sunucu zaten çalışıyor.", "en": "The server is already running."},
    "runtime.error.not_running_cant_send": {
        "tr": "Sunucu çalışmıyor, komut gönderilemedi.",
        "en": "The server isn't running, the command could not be sent.",
    },

    # -- player_panel.py -----------------------------------------------------
    "player.not_running": {
        "tr": "Oyuncu paneli için sunucu çalışıyor olmalı.",
        "en": "The server must be running for the player panel.",
    },
    "player.online_players": {"tr": "Çevrimiçi Oyuncular:", "en": "Online Players:"},
    "player.refresh_list": {"tr": "Listeyi Yenile", "en": "Refresh List"},
    "player.heal": {"tr": "İyileştir", "en": "Heal"},
    "player.kill": {"tr": "Öldür", "en": "Kill"},
    "player.feed": {"tr": "Doyur", "en": "Feed"},
    "player.damage": {"tr": "Hasar Ver", "en": "Deal Damage"},
    "player.reduce_hunger": {"tr": "Açlığı Azalt", "en": "Reduce Hunger"},
    "player.reduce_hunger_tooltip": {
        "tr": (
            "Vanilla Minecraft'ta açlığı ANINDA belirli bir değere ayarlamanın bir yolu yok — "
            "bu, oyuncuyu seçilen süre boyunca normalden daha hızlı acıktırır (yaklaşık bir etkidir)."
        ),
        "en": (
            "There's no way to set hunger to a specific value INSTANTLY in vanilla Minecraft — "
            "this makes the player get hungry faster than normal for the chosen duration "
            "(an approximate effect)."
        ),
    },
    "player.seconds_suffix": {"tr": " sn", "en": " s"},
    "player.inventory_box_title": {
        "tr": "Envanter (zırh + ikinci el dahil) — salt okunur",
        "en": "Inventory (including armor + off hand) — read-only",
    },
    "player.view_inventory": {"tr": "Envanteri Görüntüle", "en": "View Inventory"},
    "player.ender_chest_box_title": {"tr": "Ender Sandığı — salt okunur", "en": "Ender Chest — read-only"},
    "player.view_ender_chest": {"tr": "Ender Sandığını Görüntüle", "en": "View Ender Chest"},
    "player.table.section": {"tr": "Bölüm", "en": "Section"},
    "player.table.item": {"tr": "Eşya", "en": "Item"},
    "player.table.count": {"tr": "Adet", "en": "Count"},
    "player.table.slot": {"tr": "Slot", "en": "Slot"},

    # -- recommended_mods_dialog.py -----------------------------------------
    "recmods.title": {"tr": "Önerilen Modlar", "en": "Recommended Mods"},
    "recmods.info": {
        "tr": (
            "Eklediğin modla uyumlu, opsiyonel (zorunlu olmayan) modlar bulundu. "
            "İstediklerini işaretleyip ekleyebilirsin:"
        ),
        "en": (
            "Optional (not required) mods compatible with the mod you added were "
            "found. You can check the ones you want and add them:"
        ),
    },
    "recmods.add_selected": {"tr": "Seçilenleri Ekle", "en": "Add Selected"},
    "recmods.skip": {"tr": "Atla", "en": "Skip"},

    # -- library_page.py ------------------------------------------------------
    "library.content_count_chip": {"tr": "{count} içerik", "en": "{count} content"},
    "library.mod_count_chip": {"tr": "{count} mod", "en": "{count} mods"},
    "library.open_button": {"tr": "Aç", "en": "Open"},
    "library.delete_button": {"tr": "Sil", "en": "Delete"},
    "library.title": {"tr": "Pack'lerim", "en": "My Packs"},
    "library.search_placeholder": {"tr": "Pack ara...", "en": "Search packs..."},
    "library.new_pack_button": {"tr": "+ Yeni Pack", "en": "+ New Pack"},
    "library.empty_title": {"tr": "Henüz hiç pack yok", "en": "No packs yet"},
    "library.empty_subtitle": {
        "tr": '"+ Yeni Pack" ile ilk pack\'ini oluştur.',
        "en": 'Create your first pack with "+ New Pack".',
    },

    # -- instance_page.py -----------------------------------------------------
    "instance.rail.shaderpacks": {"tr": "✨ Shader Paketleri", "en": "✨ Shader Packs"},
    "instance.rail.resourcepacks": {"tr": "🖼 Görüntü Paketleri", "en": "🖼 Resource Packs"},
    "instance.rail.datapacks": {"tr": "📦 Datapack'ler", "en": "📦 Datapacks"},
    "instance.mods_search_placeholder": {"tr": "Yüklü modlarda ara...", "en": "Search installed mods..."},
    "instance.sort_hint": {
        "tr": "Sıralamak için sütun başlığına tıkla ↓",
        "en": "Click a column header to sort ↓",
    },
    "instance.show_file_names": {"tr": "Dosya adlarını göster", "en": "Show file names"},
    "common.table.mod": {"tr": "Mod", "en": "Mod"},
    "common.table.source": {"tr": "Kaynak", "en": "Source"},
    "common.table.env": {"tr": "Ortam", "en": "Environment"},
    "common.table.name": {"tr": "Ad", "en": "Name"},
    "common.remove_selected": {"tr": "Seçiliyi Kaldır", "en": "Remove Selected"},
    "instance.mods_empty_title": {"tr": "Henüz mod eklenmemiş", "en": "No mods added yet"},
    "instance.mods_empty_sub": {
        "tr": "Modrinth ve CurseForge'ta arayıp bu pack'e mod ekleyebilirsin.",
        "en": "Search Modrinth and CurseForge to add mods to this pack.",
    },
    "instance.add_mod_button": {"tr": "+ Mod Ekle", "en": "+ Add Mod"},
    "instance.vanilla_notice": {
        "tr": (
            "⚠ Vanilla pack'lerde mod eklenemez — mod eklemek için bir loader "
            "(Fabric/Quilt/Forge/NeoForge) seçerek yeni bir pack oluşturun."
        ),
        "en": (
            "⚠ Mods can't be added to vanilla packs — create a new pack with a "
            "loader (Fabric/Quilt/Forge/NeoForge) to add mods."
        ),
    },
    "instance.remove_selected_mod": {"tr": "Seçili Modu Çıkar", "en": "Remove Selected Mod"},
    "instance.fix_client_server": {"tr": "İstemci/Sunucu Düzelt", "en": "Fix Client/Server"},
    "instance.check_dependencies": {"tr": "Bağımlılıkları Kontrol Et", "en": "Check Dependencies"},
    "instance.mods_no_match": {
        "tr": '"{query}" ile eşleşen mod bulunamadı.',
        "en": 'No mods match "{query}".',
    },
    "instance.content_empty_title": {"tr": "Henüz {label} eklenmemiş", "en": "No {label} added yet"},
    "instance.content_empty_sub": {
        "tr": "Bir loader gerektirmez, vanilla pack'lere de eklenebilir.",
        "en": "Doesn't require a loader, can be added to vanilla packs too.",
    },
    "instance.content_add_button": {"tr": "+ {label} Ekle", "en": "+ Add {label}"},
    "instance.world_table_header": {"tr": "Dünya", "en": "World"},
    "instance.world_empty_title": {"tr": "Henüz dünya yüklenmemiş", "en": "No world added yet"},
    "instance.world_empty_sub": {
        "tr": (
            "Diskinden bir dünya klasörü seçebilir ya da CurseForge'ta hazır bir "
            "harita arayabilirsin."
        ),
        "en": (
            "You can pick a world folder from your disk, or search for a "
            "ready-made map on CurseForge."
        ),
    },
    "instance.world_add_local_button": {"tr": "+ Dünya Klasörü Seç", "en": "+ Select World Folder"},
    "instance.world_add_online_empty_button": {
        "tr": "+ CurseForge'ta Dünya Ara",
        "en": "+ Search Worlds on CurseForge",
    },
    "instance.world_add_online_button": {"tr": "+ CurseForge'ta Ara", "en": "+ Search on CurseForge"},
    "instance.world_remove_button": {"tr": "Seçili Dünyayı Kaldır", "en": "Remove Selected World"},
    "instance.world_source_local": {"tr": "Yerel (diskten)", "en": "Local (from disk)"},
    "instance.cheat_warning": {
        "tr": (
            "⚠ Bu bölüm hile istemcileri içerir. Sunucu kurallarını ihlal edip "
            "ban ile sonuçlanabilir — sorumluluk size aittir. Detaylar için "
            "eklerken çıkacak onay penceresini okuyun."
        ),
        "en": (
            "⚠ This section contains cheat clients. It may violate server rules "
            "and result in a ban — the responsibility is yours. Read the "
            "confirmation dialog shown when adding for details."
        ),
    },
    "instance.cheat_empty_title": {"tr": "Henüz hile modu eklenmemiş", "en": "No cheat mod added yet"},
    "instance.cheat_empty_sub": {
        "tr": "Aşağıdaki butonlarla, onay vererek Wurst ya da Meteor Client ekleyebilirsiniz.",
        "en": "Use the buttons below to add Wurst or Meteor Client after confirming.",
    },
    "instance.add_wurst_button": {"tr": "+ Wurst Client Ekle", "en": "+ Add Wurst Client"},
    "instance.add_meteor_button": {"tr": "+ Meteor Client Ekle", "en": "+ Add Meteor Client"},
    "instance.cheat_disclaimer_title": {"tr": "Sorumluluk Reddi ve Onay", "en": "Disclaimer and Confirmation"},
    "instance.cheat_disclaimer": {
        "tr": (
            "Wurst Client ve Meteor Client birer \"hile\" (cheat/utility) istemcisidir.\n\n"
            "• Bu modların kullanımı çoğu sunucunun kurallarına aykırıdır ve hesabınızın/"
            "karakterinizin o sunucudan banlanmasına yol açabilir.\n"
            "• Sadece izin verilen sunucularda ya da tek kişilik (singleplayer) "
            "dünyalarda, kendi sorumluluğunuzda kullanın.\n"
            "• MC Pack Manager ve geliştiricisi bu modların kullanımından doğacak "
            "hiçbir sonuçtan sorumlu değildir.\n\n"
            "Devam ederek bu şartları kabul etmiş olursunuz. İndirmek istiyor musunuz?"
        ),
        "en": (
            "Wurst Client and Meteor Client are \"cheat/utility\" clients.\n\n"
            "• Using these mods violates most servers' rules and may get your "
            "account/character banned from that server.\n"
            "• Use them only on servers that allow it, or in singleplayer worlds, "
            "at your own responsibility.\n"
            "• MC Pack Manager and its developer are not responsible for any "
            "consequences of using these mods.\n\n"
            "By continuing you accept these terms. Do you want to download it?"
        ),
    },
    "instance.back_button": {"tr": "← Kütüphane", "en": "← Library"},
    "instance.no_pack_selected": {"tr": "Pack seçilmedi", "en": "No pack selected"},
    "instance.export_button": {"tr": "Dışa Aktar", "en": "Export"},
    "instance.server_pack_button": {"tr": "Sunucu Paketi", "en": "Server Package"},
    "instance.sklauncher_button": {"tr": "SKLauncher ile Çalıştır", "en": "Run with SKLauncher"},
    "instance.fork_button": {"tr": "Başka Sürüme Uyarla", "en": "Adapt to Another Version"},
    "instance.fork_tooltip": {
        "tr": "Bu pack'i farklı bir Minecraft versiyonu için kopyala (fork)",
        "en": "Copy this pack for a different Minecraft version (fork)",
    },
    "instance.rail.mods": {"tr": "🧩 Modlar", "en": "🧩 Mods"},
    "instance.rail.worlds": {"tr": "🌍 Dünyalar", "en": "🌍 Worlds"},
    "instance.rail.server": {"tr": "🖥 Sunucu", "en": "🖥 Server"},
    "instance.rail.cheat_mods": {"tr": "🎯 Cheat Modları", "en": "🎯 Cheat Mods"},
    "instance.subtitle": {
        "tr": "{loader}  ·  MC {minecraft}  ·  {mod_count} mod",
        "en": "{loader}  ·  MC {minecraft}  ·  {mod_count} mods",
    },

    # -- server_section.py -----------------------------------------------------
    "server.eula_text": {
        "tr": (
            "Yerel bir sunucu çalıştırmak için Mojang'ın Minecraft Son Kullanıcı "
            "Lisans Sözleşmesi'ni (EULA) kabul etmeniz gerekir:\n\n"
            "https://www.minecraft.net/eula\n\n"
            "Kabul ederseniz bu pack için eula.txt içine eula=true yazılacaktır. "
            "Bu, Mojang/Microsoft adına değil, SİZİN kendi kararınızdır."
        ),
        "en": (
            "To run a local server you must accept Mojang's Minecraft End User "
            "License Agreement (EULA):\n\n"
            "https://www.minecraft.net/eula\n\n"
            "If you accept, eula=true will be written into eula.txt for this "
            "pack. This is YOUR own decision, not on behalf of Mojang/Microsoft."
        ),
    },
    "server.state.not_prepared": {"tr": "Henüz hazırlanmadı", "en": "Not prepared yet"},
    "server.state.needs_install": {
        "tr": "Kurulum gerekiyor (Forge/NeoForge)",
        "en": "Installation required (Forge/NeoForge)",
    },
    "server.state.ready": {"tr": "Çalıştırmaya hazır", "en": "Ready to run"},
    "server.status.stopped": {"tr": "Durduruldu", "en": "Stopped"},
    "server.status.running": {"tr": "Çalışıyor", "en": "Running"},
    "server.prepare_button": {"tr": "Hazırla / Güncelle", "en": "Prepare / Update"},
    "server.install_button": {"tr": "Kur (installServer)", "en": "Install (installServer)"},
    "server.start_button": {"tr": "Başlat", "en": "Start"},
    "server.stop_button": {"tr": "Durdur", "en": "Stop"},
    "server.mods_box_title": {"tr": "Modlar (sunucuda çalışacak)", "en": "Mods (will run on the server)"},
    "server.mods_box_title_with_count": {
        "tr": "Modlar (sunucuda çalışacak) — {count}",
        "en": "Mods (will run on the server) — {count}",
    },
    "server.mods_excluded_note": {
        "tr": "+ {count} istemci-only mod sunucu için hariç tutuldu (ör. Sodium, Iris benzeri).",
        "en": "+ {count} client-only mods excluded for the server (e.g. Sodium, Iris-like).",
    },
    "server.players_box_title": {"tr": "Oyuncular", "en": "Players"},
    "server.clear_console": {"tr": "Konsolu Temizle", "en": "Clear Console"},
    "server.console_search_placeholder": {"tr": "Konsolda ara...", "en": "Search console..."},
    "server.find_button": {"tr": "Bul", "en": "Find"},
    "server.auto_scroll": {"tr": "Otomatik Kaydır", "en": "Auto-scroll"},
    "server.command_placeholder": {
        "tr": "Sunucu komutu yazın (ör. say merhaba, op <isim>) — ↑/↓ ile geçmiş...",
        "en": "Type a server command (e.g. say hello, op <name>) — ↑/↓ for history...",
    },
    "server.send_button": {"tr": "Gönder", "en": "Send"},
    "server.settings_box_title": {"tr": "Ayarlar", "en": "Settings"},
    "server.memory_custom": {"tr": "Özel (MB)", "en": "Custom (MB)"},
    "server.memory_label": {"tr": "Bellek (RAM):", "en": "Memory (RAM):"},
    "server.no_world": {"tr": "(dünya yok)", "en": "(no world)"},
    "server.world_label": {"tr": "Dünya:", "en": "World:"},
    "server.optimized_flags_checkbox": {
        "tr": "Performans bayraklarını kullan (Aikar's flags)",
        "en": "Use performance flags (Aikar's flags)",
    },
    "server.optimized_flags_tooltip": {
        "tr": (
            "Minecraft sunucu topluluğunda yıllardır bilinen/belgeli bir G1GC JVM bayrak "
            "seti — GC duraklamalarını azaltır. run.sh/run.bat ile başlayan Forge/NeoForge "
            "kurulumlarında etkisi yoktur (onlar kendi JVM argümanlarını kullanır)."
        ),
        "en": (
            "A well-known/documented G1GC JVM flag set in the Minecraft server "
            "community — reduces GC pauses. Has no effect on Forge/NeoForge "
            "installs started via run.sh/run.bat (they use their own JVM args)."
        ),
    },
    "server.save_properties_button": {
        "tr": "server.properties'i Kaydet",
        "en": "Save server.properties",
    },
    "server.memory_info_unknown": {
        "tr": "Sistem RAM'i tespit edilemedi — üst sınır konmadı, dikkatli seçin.",
        "en": "Could not detect system RAM — no upper limit set, choose carefully.",
    },
    "server.memory_info": {
        "tr": (
            "Sisteminizde toplam ~{total_gb} GB RAM var. Sisteminiz donmasın diye "
            "sunucuya en fazla ~{max_gb} GB ayrılabiliyor (en az {reserve_gb} GB size "
            "bırakılıyor)."
        ),
        "en": (
            "Your system has ~{total_gb} GB RAM in total. To keep your system "
            "from freezing, at most ~{max_gb} GB can be allocated to the server "
            "(at least {reserve_gb} GB is left for you)."
        ),
    },

    # -- server_properties.py (bkz. gui/server_section.py, webpanel/app.py) --
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

    # -- main_window.py ---------------------------------------------------------
    "mainwindow.toolbar_name": {"tr": "Ana", "en": "Main"},
    "mainwindow.web_panel_button": {"tr": "🌐 Web Paneli", "en": "🌐 Web Panel"},
    "mainwindow.web_panel_tooltip": {
        "tr": "Sunucu yönetimi için yerel bir web paneli başlatır (kullanıcı isterse kapatabilir).",
        "en": "Starts a local web panel for server management (you can close it anytime).",
    },
    "mainwindow.settings_button": {"tr": "⚙ Ayarlar", "en": "⚙ Settings"},
    "mainwindow.open_data_folder_button": {"tr": "Veri Klasörünü Aç", "en": "Open Data Folder"},
    "mainwindow.status_ready": {"tr": "Hazır", "en": "Ready"},
    "common.cancel": {"tr": "İptal", "en": "Cancel"},
    "mainwindow.web_panel_stopped": {"tr": "Web paneli kapatıldı.", "en": "Web panel stopped."},
    "mainwindow.web_panel_close_button": {"tr": "🌐 Web Panelini Kapat", "en": "🌐 Close Web Panel"},
    "mainwindow.web_panel_started_network": {
        "tr": "Web paneli AĞA AÇIK: {url} (aynı ağdaki cihazlar şifreyle erişebilir)",
        "en": "Web panel is EXPOSED TO THE NETWORK: {url} (devices on the same network can access it with the password)",
    },
    "mainwindow.web_panel_started_local": {
        "tr": "Web paneli başlatıldı (sadece bu bilgisayar): {url}",
        "en": "Web panel started (this computer only): {url}",
    },
    "mainwindow.delete_pack_title": {"tr": "Pack'i Sil", "en": "Delete Pack"},
    "mainwindow.delete_pack_confirm": {
        "tr": "'{name}' pack'i kalıcı olarak silinsin mi?",
        "en": "Permanently delete the pack '{name}'?",
    },
    "mainwindow.pack_created": {"tr": "'{name}' oluşturuldu.", "en": "'{name}' created."},
    "mainwindow.some_mods_skipped_title": {"tr": "Bazı Modlar Atlandı", "en": "Some Mods Skipped"},
    "mainwindow.some_mods_skipped_body": {
        "tr": (
            "'{name}' pack'i oluşturuldu, ama Minecraft {minecraft} için uyumlu bir "
            "versiyonu bulunamadığından şu modlar YENİ pack'e EKLENMEDİ:\n\n{list}\n\n"
            "Bunları elle eklemeyi veya alternatif bir mod aramayı deneyin."
        ),
        "en": (
            "'{name}' pack was created, but the following mods were NOT ADDED to the "
            "NEW pack because no compatible version for Minecraft {minecraft} was "
            "found:\n\n{list}\n\nTry adding them manually or searching for an "
            "alternative mod."
        ),
    },
    "mainwindow.fork_in_progress": {
        "tr": "'{name}' Minecraft {minecraft}'e uyarlanıyor...",
        "en": "Adapting '{name}' to Minecraft {minecraft}...",
    },
    "mainwindow.server_prepared": {"tr": "Sunucu hazırlandı.", "en": "Server prepared."},
    "mainwindow.server_preparing": {
        "tr": "Sunucu hazırlanıyor (mod + sunucu dosyası indiriliyor)...",
        "en": "Preparing server (downloading mods + server file)...",
    },
    "mainwindow.error_installer_not_found": {
        "tr": "Kurulum dosyası bulunamadı — önce 'Hazırla'yı çalıştırın.",
        "en": "Installer file not found — run 'Prepare' first.",
    },
    "mainwindow.error_java_not_found": {
        "tr": "Java bulunamadı. Ayarlar'dan Java yolunu belirtin ya da PATH'e (java) ekleyin.",
        "en": "Java not found. Specify the Java path in Settings, or add it (java) to PATH.",
    },
    "mainwindow.install_complete": {"tr": "Kurulum tamamlandı.", "en": "Installation complete."},
    "mainwindow.installing": {
        "tr": "Kuruluyor (java -jar ... --installServer)... bu biraz sürebilir.",
        "en": "Installing (java -jar ... --installServer)... this may take a while.",
    },
    "mainwindow.properties_saved": {"tr": "server.properties kaydedildi.", "en": "server.properties saved."},
    "mainwindow.error_eula_not_accepted": {
        "tr": "EULA kabul edilmeden sunucu başlatılamaz.",
        "en": "The server can't be started without accepting the EULA.",
    },
    "mainwindow.error_server_not_ready": {
        "tr": "Sunucu çalıştırmaya hazır değil — önce 'Hazırla' (ve gerekiyorsa 'Kur') yapın.",
        "en": "The server isn't ready to run — run 'Prepare' (and 'Install' if needed) first.",
    },
    "mainwindow.server_starting": {"tr": "'{name}' sunucusu başlatılıyor...", "en": "Starting '{name}' server..."},
    "mainwindow.java_version_warning_title": {"tr": "Java Sürümü Uyarısı", "en": "Java Version Warning"},
    "mainwindow.java_version_warning_body": {
        "tr": (
            "Tespit edilen Java sürümü: {detected}. Minecraft {minecraft} için Java "
            "{required}+ önerilir — sunucu açılışta hata verebilir."
        ),
        "en": (
            "Detected Java version: {detected}. Java {required}+ is recommended for "
            "Minecraft {minecraft} — the server may fail to start."
        ),
    },
    "mainwindow.server_stopping": {
        "tr": "Sunucu durduruluyor (stop komutu gönderildi)...",
        "en": "Stopping server (stop command sent)...",
    },
    "mainwindow.error_inventory_timeout": {
        "tr": "{player} için envanter yanıtı alınamadı (zaman aşımı).",
        "en": "Could not get inventory response for {player} (timeout).",
    },
    "mainwindow.error_ender_chest_timeout": {
        "tr": "{player} için ender sandığı yanıtı alınamadı (zaman aşımı).",
        "en": "Could not get ender chest response for {player} (timeout).",
    },
    "mainwindow.server_stopped": {"tr": "Sunucu durdu.", "en": "Server stopped."},
    "mainwindow.server_crashed": {
        "tr": "Sunucu beklenmedik şekilde kapandı (çıkış kodu {returncode}).",
        "en": "Server exited unexpectedly (exit code {returncode}).",
    },
    "mainwindow.servers_running_title": {"tr": "Sunucular Çalışıyor", "en": "Servers Running"},
    "mainwindow.servers_running_body": {
        "tr": (
            "{count} sunucu hâlâ çalışıyor. Kapatmadan önce düzgünce durdurulsun mu?\n\n"
            "Hayır derseniz süreçler mcpack kapandıktan sonra da ÇALIŞMAYA DEVAM EDER "
            "(öksüz kalır) — kendiniz durdurmanız gerekir."
        ),
        "en": (
            "{count} server(s) still running. Stop them cleanly before closing?\n\n"
            "If you choose No, the processes will KEEP RUNNING after mcpack closes "
            "(orphaned) — you'll need to stop them yourself."
        ),
    },
    "mainwindow.select_world_folder_title": {"tr": "Dünya Klasörü Seç", "en": "Select World Folder"},
    "mainwindow.item_added": {"tr": "{name} eklendi.", "en": "{name} added."},
    "mainwindow.item_removed_named": {"tr": "{name} kaldırıldı.", "en": "{name} removed."},
    "common.removed": {"tr": "Kaldırıldı.", "en": "Removed."},
    "mainwindow.cheat_mod_searching": {
        "tr": "{label} için Minecraft {minecraft} build'i aranıyor...",
        "en": "Searching {label} build for Minecraft {minecraft}...",
    },
    "mainwindow.client_status_title": {"tr": "İstemci Durumu", "en": "Client Status"},
    "mainwindow.server_status_title": {"tr": "Sunucu Durumu", "en": "Server Status"},
    "common.warning_title": {"tr": "Uyarı", "en": "Warning"},
    "mainwindow.error_select_pack_first": {"tr": "Önce bir pack seçin.", "en": "Select a pack first."},
    "mainwindow.searching": {"tr": "Aranıyor...", "en": "Searching..."},
    "mainwindow.loading_more": {"tr": "Daha fazla yükleniyor...", "en": "Loading more..."},
    "mainwindow.already_in_pack": {"tr": "{title} zaten pack'te.", "en": "{title} is already in the pack."},
    "mainwindow.no_compatible_version": {
        "tr": "{title}: {minecraft}/{loader} için uyumlu versiyon yok",
        "en": "{title}: no compatible version for {minecraft}/{loader}",
    },
    "mainwindow.cancelled": {"tr": "Vazgeçildi.", "en": "Cancelled."},
    "mainwindow.fetching_versions": {"tr": "{title} için sürümler alınıyor...", "en": "Fetching versions for {title}..."},
    "mainwindow.latest_suffix": {"tr": " — en yeni", "en": " — latest"},
    "mainwindow.pick_version_title": {"tr": "Sürüm Seç", "en": "Pick Version"},
    "mainwindow.pick_version_body": {"tr": "'{title}' için bir sürüm seçin:", "en": "Pick a version for '{title}':"},
    "mainwindow.adding_item": {"tr": "{title} ekleniyor...", "en": "Adding {title}..."},
    "mainwindow.mod_added": {"tr": "Mod eklendi", "en": "Mod added"},
    "mainwindow.missing_required_dependency_title": {
        "tr": "Eksik Zorunlu Bağımlılık",
        "en": "Missing Required Dependency",
    },
    "mainwindow.missing_required_dependency_body": {
        "tr": (
            "Bu mod için gerekli olan bazı bağımlılıklar otomatik eklenemedi (pack'in "
            "{minecraft}/{loader} kombinasyonu için uyumlu bir versiyonları "
            "bulunamadı):\n\n{list}\n\nBu mod muhtemelen bu bağımlılıklar olmadan "
            "çalışmayacaktır — elle eklemeyi deneyin ya da uyumlu bir Minecraft/loader "
            "versiyonu seçin."
        ),
        "en": (
            "Some dependencies required by this mod could not be added automatically "
            "(no compatible version was found for the pack's {minecraft}/{loader} "
            "combination):\n\n{list}\n\nThis mod likely won't work without these "
            "dependencies — try adding them manually or pick a compatible "
            "Minecraft/loader version."
        ),
    },
    "mainwindow.no_compatible_version_simple": {
        "tr": "{title}: {minecraft} için uyumlu versiyon yok",
        "en": "{title}: no compatible version for {minecraft}",
    },
    "mainwindow.downloading_item": {"tr": "{title} indiriliyor...", "en": "Downloading {title}..."},
    "mainwindow.world_added": {"tr": "Dünya eklendi", "en": "World added"},
    "common.added": {"tr": "Eklendi", "en": "Added"},
    "mainwindow.pick_source_dir_title": {
        "tr": "Overrides kaynak klasörü (config, kubejs, defaultconfigs, ...)",
        "en": "Overrides source folder (config, kubejs, defaultconfigs, ...)",
    },
    "mainwindow.cancelling": {"tr": "İptal ediliyor...", "en": "Cancelling..."},
    "mainwindow.missing_required_deps_title": {
        "tr": "Eksik Zorunlu Bağımlılıklar",
        "en": "Missing Required Dependencies",
    },
    "mainwindow.missing_required_deps_confirm_body": {
        "tr": (
            "Bu pack'teki bazı modların gerektirdiği zorunlu bağımlılıklar pack'te "
            "yok. Bu haliyle export edilirse oyun büyük ihtimalle açılışta "
            "çökecektir:\n\n{list}\n\nYine de devam etmek istiyor musunuz?"
        ),
        "en": (
            "Some mods in this pack require mandatory dependencies that aren't in "
            "the pack. If exported as-is, the game will likely crash on "
            "startup:\n\n{list}\n\nDo you want to continue anyway?"
        ),
    },
    "mainwindow.checking_dependencies": {"tr": "Bağımlılıklar kontrol ediliyor...", "en": "Checking dependencies..."},
    "mainwindow.dependency_check_title": {"tr": "Bağımlılık Kontrolü", "en": "Dependency Check"},
    "mainwindow.dependency_check_ok": {
        "tr": "Sorun yok — pack'teki hiçbir modun bilinen, eksik bir zorunlu bağımlılığı yok.",
        "en": "No problems — none of the mods in the pack have a known missing required dependency.",
    },
    "mainwindow.missing_required_deps_info_body": {
        "tr": (
            "Şu modların gerektirdiği zorunlu bağımlılıklar pack'te yok — bu haliyle "
            "export edilirse oyun büyük ihtimalle açılışta çökecektir:\n\n{list}"
        ),
        "en": (
            "The mandatory dependencies required by these mods aren't in the pack — "
            "if exported as-is, the game will likely crash on startup:\n\n{list}"
        ),
    },
    "mainwindow.export_dialog_title": {"tr": "Dışa Aktar", "en": "Export"},
    "mainwindow.export_done": {"tr": "Tamamlandı: {path}", "en": "Done: {path}"},
    "mainwindow.exporting": {"tr": "Dışa aktarılıyor...", "en": "Exporting..."},
    "mainwindow.add_world_title": {"tr": "Dünya Ekle", "en": "Add World"},
    "mainwindow.add_world_body": {
        "tr": "Bu pack'e yüklenmiş dünya var. Sunucu paketine bir dünya eklemek ister misiniz?",
        "en": "This pack has an uploaded world. Do you want to add a world to the server package?",
    },
    "mainwindow.pick_world_title": {"tr": "Dünya Seç", "en": "Pick World"},
    "mainwindow.pick_world_body": {
        "tr": "Sunucu paketine eklenecek dünyayı seçin:",
        "en": "Pick the world to add to the server package:",
    },
    "mainwindow.confirm_world_title": {"tr": "Dünyayı Onayla", "en": "Confirm World"},
    "mainwindow.confirm_world_body": {
        "tr": '\'{name}\' dünyası pakette "world" adıyla dışa aktarılacak. Onaylıyor musunuz?',
        "en": "The world '{name}' will be exported as \"world\" in the package. Do you confirm?",
    },
    "mainwindow.server_pack_dialog_title": {"tr": "Sunucu Paketi Oluştur", "en": "Create Server Package"},
    "mainwindow.server_pack_done": {"tr": "Sunucu paketi hazır: {path}", "en": "Server package ready: {path}"},
    "mainwindow.server_pack_building": {"tr": "Sunucu paketi oluşturuluyor...", "en": "Building server package..."},
    "mainwindow.server_file_missing_title": {
        "tr": "Sunucu Dosyası Otomatik İndirilemedi",
        "en": "Server File Could Not Be Auto-Downloaded",
    },
    "mainwindow.server_file_missing_body": {
        "tr": (
            "Sunucu paketi oluşturuldu, ama bu Minecraft/loader kombinasyonu için "
            "resmi sunucu dosyası otomatik bulunup indirilemedi (ağ hatası ya da bu "
            "versiyon için resmi bir dosya yayınlanmamış olabilir).\n\nZip içindeki "
            "'{notice_name}' dosyasında detay ve elle indirme talimatı var."
        ),
        "en": (
            "The server package was created, but the official server file for this "
            "Minecraft/loader combination could not be automatically found and "
            "downloaded (network error, or no official file may have been published "
            "for this version).\n\nSee the '{notice_name}' file inside the zip for "
            "details and manual download instructions."
        ),
    },
    "mainwindow.error_sklauncher_path_missing": {
        "tr": "Önce Ayarlar'dan SKLauncher yolunu belirleyin.",
        "en": "Set the SKLauncher path in Settings first.",
    },
    "mainwindow.instance_ready": {
        "tr": "Instance hazır: {instance_dir} — SKLauncher başlatılıyor",
        "en": "Instance ready: {instance_dir} — starting SKLauncher",
    },
    "mainwindow.instance_preparing": {"tr": "Instance hazırlanıyor...", "en": "Preparing instance..."},
    "common.error_title": {"tr": "Hata", "en": "Error"},

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
