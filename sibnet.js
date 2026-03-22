function linkiCoz(htmlKaynakKodu) {
    var regex1 = /player\.src\(\s*\[\s*\{\s*src\s*:\s*["']([^"']+)["']/;
    var eslesme = regex1.exec(htmlKaynakKodu);
    
    if (!eslesme) {
        var regex2 = /src\s*:\s*["'](\/v\/[^"']+\.mp4)["']/;
        eslesme = regex2.exec(htmlKaynakKodu);
    }

    if (eslesme && eslesme[1]) {
        var link = eslesme[1];
        if (link.startsWith("/")) return "https://video.sibnet.ru" + link;
        return link;
    }
    return "BULUNAMADI";
}
