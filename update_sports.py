import requests
import json
import re

# --- AYARLAR ---
URLS = [
    "https://cdn.jsdelivr.net/gh/Playtvapp/Playdeneme@main/justintv_proxy_kanallar.m3u8"
]

OUTPUT_FILE = "mac_listesi.json"

def normalize_text(text):
    """
    Kanal ismini karşılaştırma için sadeleştirir.
    Örn: 'Fenerbahçe' -> 'fenerbahce'
    """
    if not text: return ""
    text = text.lower()
    tr_map = str.maketrans("çğıöşü", "cgiosu")
    text = text.translate(tr_map)
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

def clean_name(name):
    """
    Kanal ismini ekranda güzel görünecek şekilde temizler.
    """
    # Köşeli ve normal parantezleri sil
    name = re.sub(r'\[.*?\]', '', name)
    name = re.sub(r'\(.*?\)', '', name)

    # Gereksiz ekleri sil
    bad_words = [
        'TR:', 'TR ', 'tr:', 'tr ', '|', '-', 'HD', 'FHD', 'SD', '4K', 'HEVC', 
        '1080p', '720p', 'HQ', 'VIP', 'CANLI', 'YENI', 'GUNCEL', 'BACKUP',
        'UK:', 'USA:', 'DE:', 'IT:', 'FR:'
    ]

    for word in bad_words:
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        name = pattern.sub('', name)

    name = name.strip()
    name = re.sub(' +', ' ', name) # Çift boşlukları teke düşür
    return name

def parse_m3u(url):
    print(f"İndiriliyor: {url}")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        content = response.text.splitlines()
    except Exception as e:
        print(f"HATA - Link bozuk: {url} | {e}")
        return []

    channels = []
    current_channel = {}
    current_headers = {} # Header'ları (User-Agent, Referer vb.) geçici olarak tutacak sözlük

    for line in content:
        line = line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF"):
            # 1. KATEGORİ (GROUP-TITLE) ALMA
            group_match = re.search(r'group-title="([^"]+)"', line)
            if group_match:
                raw_group = group_match.group(1).strip()
            else:
                raw_group = "Diğer"

            # 2. LOGO ALMA
            logo_match = re.search(r'tvg-logo="([^"]+)"', line)
            logo = logo_match.group(1) if logo_match else ""

            # 3. İSİM ALMA
            raw_name = line.split(",")[-1].strip()

            current_channel = {
                "display_name": clean_name(raw_name),
                "normalized_name": normalize_text(clean_name(raw_name)),
                "category": raw_group,
                "logo": logo
            }
            # Yeni kanala geçildiğinde header sıfırlanır
            current_headers = {} 

        # --- HEADER (USER-AGENT, REFERER) YAKALAMA BÖLÜMÜ ---
        elif line.startswith("#EXTVLCOPT:"):
            match = re.match(r'#EXTVLCOPT:([^=]+)=(.*)', line)
            if match:
                key = match.group(1).strip().lower()
                val = match.group(2).strip()
                if key == "http-user-agent":
                    current_headers["User-Agent"] = val
                elif key == "http-referrer":
                    current_headers["Referer"] = val
                elif key == "http-origin":
                    current_headers["Origin"] = val
                else:
                    current_headers[key.title()] = val # Diğer olası headerlar için

        elif line.startswith("#EXT-X-REFERER:"):
            current_headers["Referer"] = line.split(":", 1)[1].strip()
            
        elif line.startswith("#EXT-X-USER-AGENT:"):
            current_headers["User-Agent"] = line.split(":", 1)[1].strip()

        # --- LİNK (URL) YAKALAMA BÖLÜMÜ ---
        elif line.startswith("http") or line.startswith("rtmp"):
            if current_channel:
                url_part = line
                
                # BAZI LİNKLERDE URL SONUNDA PIPE (|) İLE HEADER GÖNDERİLİR. BUNU DA AYIKLIYORUZ.
                if "|" in url_part:
                    parts = url_part.split("|", 1)
                    url_part = parts[0]
                    h_str = parts[1]
                    
                    # pipe sonrası genelde User-Agent=X&Referer=Y şeklindedir
                    for h_kv in h_str.split("&"):
                        if "=" in h_kv:
                            k, v = h_kv.split("=", 1)
                            k_lower = k.lower()
                            if k_lower == "user-agent": current_headers["User-Agent"] = v
                            elif k_lower == "referer": current_headers["Referer"] = v
                            elif k_lower == "origin": current_headers["Origin"] = v
                            else: current_headers[k] = v

                current_channel["url"] = url_part
                current_channel["headers"] = current_headers.copy() # Ayıklanan headerları kanala ekle
                
                channels.append(current_channel)
                current_channel = {}
                current_headers = {}

    return channels

def main():
    all_data = {} 

    for url in URLS:
        channels = parse_m3u(url)

        for ch in channels:
            cat = ch["category"]
            d_name = ch["display_name"]
            n_name = ch["normalized_name"]

            if len(d_name) < 2:
                continue

            if cat not in all_data:
                all_data[cat] = []

            # --- EŞLEŞTİRME VE BİRLEŞTİRME ---
            found = False
            for existing_ch in all_data[cat]:
                existing_norm = existing_ch.get("normalized_key", normalize_text(existing_ch["name"]))

                if n_name == existing_norm:
                    # Varsa yeni kaynak ekle (Yeni kaynağın kendi özel headerlarını da ekliyoruz)
                    existing_ch["sources"].append({
                        "url": ch["url"],
                        "label": f"Kaynak {len(existing_ch['sources']) + 1}",
                        "headers": ch["headers"]
                    })
                    # Logo eksikse tamamla
                    if not existing_ch["logo"] and ch["logo"]:
                        existing_ch["logo"] = ch["logo"]

                    found = True
                    break

            if not found:
                # Yoksa yeni oluştur (Header bilgisiyle birlikte)
                new_entry = {
                    "name": d_name,
                    "normalized_key": n_name,
                    "logo": ch["logo"],
                    "sources": [
                        {
                            "url": ch["url"],
                            "label": "Kaynak 1",
                            "headers": ch["headers"]
                        }
                    ]
                }
                all_data[cat].append(new_entry)

    # JSON ÇIKTISINI TEMİZLEME
    final_output = {}
    sorted_categories = sorted(all_data.keys())

    for cat in sorted_categories:
        items = all_data[cat]
        final_output[cat] = []
        for item in items:
            # normalized_key'i sil
            if "normalized_key" in item:
                del item["normalized_key"]
            final_output[cat].append(item)

    # KAYDET
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)

    print(f"Bitti! Dosya hazır: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
