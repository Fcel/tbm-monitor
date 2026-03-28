"""
TBM İzleme Sayfası — Blue Line TN07
Güzergah: LandXML (DUb DLTM / EPSG:3997)
Her halka: 1.8 m
Halka başlangıç chainagei: 308+771.62 m
"""

import math
import xml.etree.ElementTree as ET

import folium
import streamlit as st
from streamlit_folium import st_folium
from supabase import create_client

st.set_page_config(page_title="TBM İzleme", layout="wide", page_icon="🚇")

HALKA_UZUNLUK      = 1.8
HALKA_BASLANGIC_CH = 308_771.62
EPSG_PROJE         = 3997
TBM_CAPI           = 6.5
TBM_UZUNLUK        = 8.9
TUNEL_CAPI         = 9.61

LANDXML_TN07 = r"""<LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2" version="1.2">
<Alignments>
<Alignment name="RLE _TN07_1" length="1426.448145256" staStart="307557.958300000" state="proposed">
<CoordGeom name="RLE _TN07_1" state="proposed">
<Line length="802.056000000" dir="3.388637062" staStart="307557.958300000">
  <Start>2785391.237538632 507777.352116356 0.0</Start>
  <End>2784613.532428970 507581.218005246 0.0</End>
</Line>
<Spiral length="63.977592461" radiusEnd="399.924000000" radiusStart="INF" rot="ccw"
  spiType="clothoid" dirStart="3.388637062" dirEnd="3.308649874" staStart="308360.014300000">
  <Start>2784613.532428970 507581.218005246 0.0</Start>
  <End>2784551.119968936 507567.236233594 0.0</End>
</Spiral>
<Curve rot="ccw" crvType="arc" length="288.892048276"
  dirStart="3.308649874" dirEnd="2.586282503" radius="399.924000000">
  <Start>2784551.119968936 507567.236233594 0.0</Start>
  <Center>2784484.620101668 507961.592637662 0.0</Center>
  <End>2784273.777420651 507621.762430591 0.0</End>
</Curve>
<Spiral length="63.977592510" radiusEnd="INF" radiusStart="399.924000000" rot="ccw"
  spiType="clothoid" dirStart="2.586282503" dirEnd="2.506295315" staStart="308712.883940738">
  <Start>2784273.777420651 507621.762430591 0.0</Start>
  <End>2784221.303310298 507658.331172090 0.0</End>
</Spiral>
<Line length="207.544912009" dir="2.506295315" staStart="308776.861533247">
  <Start>2784221.303310298 507658.331172090 0.0</Start>
  <End>2784054.251388929 507781.491823548 0.0</End>
</Line>
</CoordGeom>
</Alignment>
</Alignments>
</LandXML>"""


class Guzergah:
    def __init__(self, xml_str: str):
        self.elemanlar: list[dict] = []
        self.sta_bas = 0.0
        self.uzunluk = 0.0
        self._parse(xml_str)
        self.cizgi = self._uret_cizgi(adim=3.0)

    def _parse(self, xml_str: str):
        xml_str = xml_str.replace(' xmlns="http://www.landxml.org/schema/LandXML-1.2"', "")
        kok = ET.fromstring(xml_str)
        hizalama = kok.find(".//Alignment")
        self.sta_bas = float(hizalama.get("staStart"))
        self.uzunluk = float(hizalama.get("length"))
        simdiki = self.sta_bas
        for e in hizalama.find("CoordGeom"):
            tag = e.tag
            if tag == "Line":
                uzun = float(e.get("length"))
                sta  = float(e.get("staStart", simdiki))
                self.elemanlar.append({"tip": "Line", "sta": sta, "uzun": uzun,
                    "bas": self._p(e, "Start"), "son": self._p(e, "End"), "yon": float(e.get("dir"))})
                simdiki = sta + uzun
            elif tag == "Curve":
                uzun = float(e.get("length"))
                self.elemanlar.append({"tip": "Curve", "sta": simdiki, "uzun": uzun,
                    "bas": self._p(e, "Start"), "son": self._p(e, "End"),
                    "merkez": self._p(e, "Center"), "R": float(e.get("radius")),
                    "donus": e.get("rot"), "yonBas": float(e.get("dirStart"))})
                simdiki += uzun
            elif tag == "Spiral":
                uzun = float(e.get("length"))
                sta  = float(e.get("staStart", simdiki))
                rS, rE = e.get("radiusStart", "INF"), e.get("radiusEnd", "INF")
                self.elemanlar.append({"tip": "Spiral", "sta": sta, "uzun": uzun,
                    "bas": self._p(e, "Start"), "son": self._p(e, "End"),
                    "donus": e.get("rot"),
                    "rBas": float("inf") if rS == "INF" else float(rS),
                    "rSon": float("inf") if rE == "INF" else float(rE),
                    "yonBas": float(e.get("dirStart")), "yonSon": float(e.get("dirEnd"))})
                simdiki = sta + uzun

    @staticmethod
    def _p(elem, child_tag):
        parts = elem.find(child_tag).text.strip().split()
        return (float(parts[0]), float(parts[1]))

    def konum(self, ch: float):
        for e in self.elemanlar:
            sta_s, sta_e = e["sta"], e["sta"] + e["uzun"]
            if not (sta_s <= ch <= sta_e + 1e-6):
                continue
            off = ch - sta_s
            if e["tip"] == "Line":
                t = off / e["uzun"]
                return (e["bas"][0] + t*(e["son"][0]-e["bas"][0]),
                        e["bas"][1] + t*(e["son"][1]-e["bas"][1]))
            elif e["tip"] == "Curve":
                Nc, Ec = e["merkez"]; Ns, Es = e["bas"]; R = e["R"]
                alfa = math.atan2(Ns-Nc, Es-Ec) + (1 if e["donus"]=="ccw" else -1)*(off/R)
                return Nc + R*math.sin(alfa), Ec + R*math.cos(alfa)
            elif e["tip"] == "Spiral":
                t = off / e["uzun"]
                return (e["bas"][0] + t*(e["son"][0]-e["bas"][0]),
                        e["bas"][1] + t*(e["son"][1]-e["bas"][1]))
        return None

    def azimut(self, ch: float) -> float:
        for e in self.elemanlar:
            sta_s, sta_e = e["sta"], e["sta"] + e["uzun"]
            if not (sta_s <= ch <= sta_e + 1e-6):
                continue
            off = ch - sta_s
            if e["tip"] == "Line":
                return e["yon"]
            elif e["tip"] == "Curve":
                return e["yonBas"] + (-1 if e["donus"]=="ccw" else 1)*(off/e["R"])
            elif e["tip"] == "Spiral":
                t = off / e["uzun"]
                return e["yonBas"] + t*(e["yonSon"]-e["yonBas"])
        return 0.0

    def tbm_konumu(self, halka_no: int):
        # TBM arka kenarı son ringin önünde; merkez yarı boy kadar daha ileride
        ch = HALKA_BASLANGIC_CH - halka_no * HALKA_UZUNLUK - TBM_UZUNLUK / 2
        pt = self.konum(ch)
        return None if pt is None else (pt[0], pt[1], self.azimut(ch), ch)

    def _uret_cizgi(self, adim=3.0):
        pts, sta_son = [], self.sta_bas + self.uzunluk
        ch = self.sta_bas
        while ch <= sta_son:
            pt = self.konum(ch)
            if pt: pts.append((pt[0], pt[1], ch))
            ch += adim
        pt = self.konum(sta_son)
        if pt: pts.append((pt[0], pt[1], sta_son))
        return pts


@st.cache_resource
def _donusturucu():
    from pyproj import Transformer
    return Transformer.from_crs(EPSG_PROJE, 4326, always_xy=True)

def dikdortgen_koseler(lat, lon, yon_rad, uzunluk, genislik, merkez_ofseti=0.0):
    """Verilen merkez ofsetine göre döndürülmüş dikdörtgen köşelerini WGS84 cinsinden döndürür.
    merkez_ofseti: ileri yönde TBM merkezinden metre cinsinden kaydırma (+ileri, -geri)."""
    yar_u = uzunluk / 2
    yar_g = genislik / 2
    ileri = (math.sin(yon_rad), math.cos(yon_rad))   # (dE, dN)
    sag   = (math.cos(yon_rad), -math.sin(yon_rad))
    lat_rad = math.radians(lat)
    m_per_lat = 111320.0
    m_per_lon = 111320.0 * math.cos(lat_rad)
    cx = merkez_ofseti * ileri[0]
    cy = merkez_ofseti * ileri[1]
    def offset(dE, dN):
        return [lat + (dN + cy) / m_per_lat, lon + (dE + cx) / m_per_lon]
    return [
        offset( yar_u*ileri[0] + yar_g*sag[0],  yar_u*ileri[1] + yar_g*sag[1]),
        offset( yar_u*ileri[0] - yar_g*sag[0],  yar_u*ileri[1] - yar_g*sag[1]),
        offset(-yar_u*ileri[0] - yar_g*sag[0], -yar_u*ileri[1] - yar_g*sag[1]),
        offset(-yar_u*ileri[0] + yar_g*sag[0], -yar_u*ileri[1] + yar_g*sag[1]),
    ]

def koridor_polygon_wgs(guzergah, ch_bas, ch_son, genislik, adim=3.0):
    """ch_bas'tan ch_son'a güzergah eğrisini izleyen kıvrımlı koridor polygonu döndürür."""
    if ch_son <= ch_bas:
        return []
    yar_g = genislik / 2
    chainages, ch = [], ch_bas
    while ch <= ch_son + 1e-6:
        chainages.append(min(ch, ch_son))
        ch += adim
    if chainages[-1] < ch_son:
        chainages.append(ch_son)
    sag, sol = [], []
    for c in chainages:
        pt = guzergah.konum(c)
        if pt is None:
            continue
        N, E = pt
        az = guzergah.azimut(c)
        la_s, lo_s = proje2wgs(N - math.sin(az)*yar_g, E + math.cos(az)*yar_g)
        la_l, lo_l = proje2wgs(N + math.sin(az)*yar_g, E - math.cos(az)*yar_g)
        if la_s: sag.append([la_s, lo_s])
        if la_l: sol.append([la_l, lo_l])
    return sag + sol[::-1] if sag and sol else []

def rings_geojson(guzergah, halka_no):
    """Tamamlanan halkaları GeoJSON FeatureCollection olarak döndürür."""
    features = []
    for i in range(halka_no):
        ch_son = HALKA_BASLANGIC_CH - i * HALKA_UZUNLUK
        ch_bas = ch_son - HALKA_UZUNLUK
        pts = koridor_polygon_wgs(guzergah, ch_bas, ch_son, TUNEL_CAPI, adim=0.9)
        if not pts:
            continue
        # GeoJSON koordinatları [lon, lat] sıralamasında olmalı
        coords = [[p[1], p[0]] for p in pts]
        coords.append(coords[0])
        features.append({
            "type": "Feature",
            "properties": {
                "ring": i,
                "ch": ch_fmt(ch_son),
                "cift": i % 2
            },
            "geometry": {"type": "Polygon", "coordinates": [coords]}
        })
    return {"type": "FeatureCollection", "features": features}

def proje2wgs(N, E):
    try:
        lon, lat = _donusturucu().transform(E, N)
        if -90 < lat < 90 and -180 < lon < 180:
            return lat, lon
    except Exception:
        pass
    return None, None

def guzergah_wgs84(cizgi):
    out = []
    for N, E, _ in cizgi:
        la, lo = proje2wgs(N, E)
        if la is not None: out.append([la, lo])
    return out


def ch_fmt(ch_m: float) -> str:
    km = int(ch_m // 1000)
    m  = ch_m - km * 1000
    return f"{km}+{m:06.2f}"

@st.cache_resource
def _supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def halka_yukle() -> int:
    try:
        r = _supabase().table("tbm_durum").select("halka_no").eq("id", 1).single().execute()
        return int(r.data["halka_no"])
    except Exception:
        return 0

def halka_kaydet(n: int):
    _supabase().table("tbm_durum").upsert({"id": 1, "halka_no": n}).execute()

st.title("🚇 TBM İzleme — Blue Line TN07")
guzergah  = Guzergah(LANDXML_TN07)
sta_son   = guzergah.sta_bas + guzergah.uzunluk
max_halka = int((HALKA_BASLANGIC_CH - guzergah.sta_bas) / HALKA_UZUNLUK)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Güzergah Uzunluğu",   f"{guzergah.uzunluk:.1f} m")
c2.metric("Halka Başlangıç Ch.", ch_fmt(HALKA_BASLANGIC_CH))
c3.metric("Güzergah Başlangıç Ch.", ch_fmt(guzergah.sta_bas))
c4.metric("Tahmini Maks. Halka", max_halka)
st.divider()

kayitli_halka = halka_yukle()
halka_no = st.number_input("🔢 Halka Numarası (Ring No)",
    min_value=0, max_value=max(max_halka+50, 500), value=kayitli_halka, step=1,
    help=f"Ring 0 → Ch {ch_fmt(HALKA_BASLANGIC_CH)}  |  Ring {max_halka} → Ch {ch_fmt(guzergah.sta_bas)}")

with st.expander("🔐 Admin — Ring Güncelle"):
    sifre = st.text_input("Şifre", type="password", key="admin_sifre")
    if sifre == st.secrets.get("ADMIN_SIFRE", ""):
        yeni_halka = st.number_input("Yeni Halka No",
            min_value=0, max_value=max(max_halka+50, 500),
            value=kayitli_halka, step=1, key="admin_halka")
        if st.button("💾 Kaydet"):
            halka_kaydet(yeni_halka)
            st.success(f"Ring {yeni_halka} kaydedildi.")
            st.rerun()
    elif sifre:
        st.error("Şifre yanlış.")

ch_son_ring   = HALKA_BASLANGIC_CH - halka_no * HALKA_UZUNLUK   # son ring arka kenarı
ch_cutter     = ch_son_ring - TBM_UZUNLUK                        # cutter head
ch_tbm        = ch_son_ring - TBM_UZUNLUK / 2                    # TBM merkezi (çizim için)
konum         = guzergah.tbm_konumu(halka_no)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Halka No", halka_no)
k2.metric("Son Ring Arka Kenarı", ch_fmt(ch_son_ring))
k3.metric("Cutter Head", ch_fmt(ch_cutter))
k4.metric("Toplam Tünel Metrajı", f"{halka_no * HALKA_UZUNLUK + TBM_UZUNLUK:.2f} m")

if ch_cutter < guzergah.sta_bas:
    st.warning(f"⚠️ Halka {halka_no} güzergah dışında (Ch {ch_fmt(ch_tbm)} < başlangıç {ch_fmt(guzergah.sta_bas)}).")
st.divider()

if konum:
    N_tbm, E_tbm, yon_rad, ch = konum
    lat_tbm, lon_tbm = proje2wgs(N_tbm, E_tbm)
    if lat_tbm is not None:
        m = folium.Map(location=[lat_tbm, lon_tbm], zoom_start=17, tiles="OpenStreetMap")
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri", name="Uydu", overlay=False, control=True).add_to(m)
        folium.TileLayer("OpenStreetMap", name="Sokak Haritası").add_to(m)
        cizgi_wgs = guzergah_wgs84(guzergah.cizgi)
        if cizgi_wgs:
            folium.PolyLine(cizgi_wgs, color="#1565C0", weight=5, opacity=0.85,
                tooltip="TN07 Tünel Güzergahı").add_to(m)
        for pt_ne, etiket, renk, simge in [
            (guzergah.konum(guzergah.sta_bas), f"Başlangıç Şaftı Ch:{ch_fmt(guzergah.sta_bas)}", "green", "home"),
            (guzergah.konum(sta_son), f"Bitiş Şaftı Ch:{ch_fmt(sta_son)}", "blue", "flag")]:
            if pt_ne:
                la, lo = proje2wgs(*pt_ne)
                if la: folium.Marker([la, lo], tooltip=etiket,
                    icon=folium.Icon(color=renk, icon=simge, prefix="fa")).add_to(m)
        # TBM azalan chainage yönünde ilerliyor → 180° çevir
        yon_tbm = yon_rad + math.pi
        yon_derece = math.degrees(yon_tbm) % 360
        # TBM gövdesi — 13m × 10m
        folium.Polygon(
            locations=dikdortgen_koseler(lat_tbm, lon_tbm, yon_tbm, TBM_UZUNLUK, 10.0),
            color="#D32F2F", weight=2,
            fill=True, fill_color="#EF5350", fill_opacity=0.85,
            tooltip=f"TBM | Ring: {halka_no} | {yon_derece:.1f}° | Ch {ch_fmt(ch)}"
        ).add_to(m)
        # Tamamlanan halkalar — her ring ayrı polygon, çift/tek renk
        if halka_no > 0:
            gc = rings_geojson(guzergah, halka_no)
            folium.GeoJson(
                gc,
                style_function=lambda f: {
                    "fillColor": "#78909C" if f["properties"]["cift"] else "#B0BEC5",
                    "color": "#37474F",
                    "weight": 0.8,
                    "fillOpacity": 0.80,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=["ring", "ch"],
                    aliases=["Ring:", "Chainage:"],
                    localize=True
                ),
                name="Tamamlanan Halkalar"
            ).add_to(m)
        folium.LayerControl().add_to(m)
        st_folium(m, width="100%", height=620, key="tbm_harita")
    else:
        st.error(f"⚠️ EPSG:{EPSG_PROJE} → WGS84 dönüşümü başarısız.")
        st.info(f"Ham koordinatlar: N=`{N_tbm:.3f}`, E=`{E_tbm:.3f}`\nQGIS'te WGS84 karşılığını bulup bildirin.")
        with st.expander("🔧 Tüm güzergah noktaları (ham)"):
            for N, E, sta in guzergah.cizgi[::10]:
                st.write(f"Ch {sta:.1f} m → N={N:.3f}, E={E:.3f}")
else:
    st.info(f"Ring {halka_no} güzergah dışında. Geçerli aralık: 0–{max_halka}")
