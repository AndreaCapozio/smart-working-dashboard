import os
import warnings
import urllib.parse
import math
import datetime

import gradio as gr
import pandas as pd
import requests

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Insieme dei mezzi che prevedono parcheggio e pedaggio
AUTO_TYPES = {"Auto benzina", "Auto diesel", "Auto GPL", "Auto hybrid", "Auto elettrica", "Moto"}

DEFAULT_TRANSPORT_DF = pd.DataFrame([
    {"Mezzo": "Auto benzina",  "Consumo_medio": "~6,5 L/100km",   "Costo": 0.12, "CO2_km": 170, "Unita_Costo": "KM"},
    {"Mezzo": "Auto diesel",   "Consumo_medio": "~5,0 L/100km",   "Costo": 0.10, "CO2_km": 150, "Unita_Costo": "KM"},
    {"Mezzo": "Auto GPL",      "Consumo_medio": "~8 L/100km",     "Costo": 0.09, "CO2_km": 120, "Unita_Costo": "KM"},
    {"Mezzo": "Auto hybrid",   "Consumo_medio": "~4,0 L/100km",   "Costo": 0.08, "CO2_km": 90,  "Unita_Costo": "KM"},
    {"Mezzo": "Auto elettrica","Consumo_medio": "~15 kWh/100km",  "Costo": 0.05, "CO2_km": 40,  "Unita_Costo": "KM"},
    {"Mezzo": "Moto",          "Consumo_medio": "~4 L/100km",     "Costo": 0.07, "CO2_km": 70,  "Unita_Costo": "KM"},
    {"Mezzo": "Trasporto Pubblico","Consumo_medio": "~35-40 L/100km", "Costo": 1.50, "CO2_km": 90,  "Unita_Costo": "1,5€ per ogni 100 minuti"},
    {"Mezzo": "Monopattino",   "Consumo_medio": "~1-2 kWh/100km", "Costo": 0.02, "CO2_km": 14,  "Unita_Costo": "KM"},
    {"Mezzo": "Bicicletta",    "Consumo_medio": "N/A",            "Costo": 0.00, "CO2_km": 0,   "Unita_Costo": "KM"},
    {"Mezzo": "Piedi",         "Consumo_medio": "N/A",            "Costo": 0.00, "CO2_km": 0,   "Unita_Costo": "KM"},
])

DEFAULT_REMOTE_COSTS = {
    "energia": 0.85,
    "pranzo_casa": 5.50,
    "settimane_anno": 48,
}

TICKET_MODES = [
    "Solo giorni in presenza",
    "Solo giorni in smart working",
    "Entrambi (presenza e smart)",
]

# ─────────────────────────────────────────────
# HELPER DI FORMATTAZIONE
# ─────────────────────────────────────────────

def format_num(v: float) -> str:
    """Formatta un numero con separatori italiani (es. 1.234,56)."""
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_euro(v: float) -> str:
    """Formatta un valore monetario in euro con separatori italiani."""
    return f"{format_num(v)} €"

def format_html_delta(v: float) -> str:
    """Restituisce un delta colorato in HTML: rosso se negativo, verde se positivo."""
    a = format_num(abs(v))
    if v < 0:
        return f"<span style='color:#ff4b4b;font-weight:bold;'>-{a} €</span>"
    elif v > 0:
        return f"<span style='color:#09ab3b;font-weight:bold;'>+{a} €</span>"
    return "<b>0,00 €</b>"

# ─────────────────────────────────────────────
# GEOCODING E ROUTING
# ─────────────────────────────────────────────

def search_address_nominatim(query):
    """Geocodifica un indirizzo tramite Nominatim (OpenStreetMap). Ritorna lista di risultati JSON."""
    if not query:
        return []
    if not isinstance(query, str):
        query = str(query)
    query = query.strip()
    if len(query) < 3:
        return []
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=5"
    try:
        r = requests.get(url, headers={"User-Agent": "SmartWorkDashboard/2.0"}, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []

def get_route_osm(lat1, lon1, lat2, lon2, vehicle: str):
    """
    Calcola durata (minuti) e distanza (km) tramite OSRM (OpenStreetMap Routing Machine).
    Seleziona il profilo di routing in base al mezzo: cycling, walking o driving.
    """
    profile = {"Bicicletta": "cycling", "Monopattino": "cycling", "Piedi": "walking"}.get(vehicle, "driving")
    url = f"https://router.project-osrm.org/route/v1/{profile}/{lon1},{lat1};{lon2},{lat2}?overview=false"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get("routes"):
                rt = data["routes"][0]
                secs = int(rt["duration"])
                return secs / 60.0, rt["distance"] / 1000.0
    except Exception:
        pass
    return 0.0, 0.0

def get_route_gmaps(start_addr, end_addr, vehicle, api_key, dep_time_str):
    """
    Calcola durata (minuti) e distanza (km) tramite Google Maps Directions API.
    start_addr e end_addr possono essere stringhe o liste: viene estratto sempre il primo elemento.
    """
    if isinstance(start_addr, (list, tuple)):
        start_addr = start_addr[0]
    if isinstance(end_addr, (list, tuple)):
        end_addr = end_addr[0]
    start_addr = str(start_addr)
    end_addr = str(end_addr)

    mode = "driving"
    if vehicle in ["Bicicletta", "Monopattino"]:
        mode = "bicycling"
    elif vehicle == "Piedi":
        mode = "walking"
    elif vehicle == "Trasporto Pubblico":
        mode = "transit"

    now = datetime.datetime.now()
    try:
        h, m = map(int, dep_time_str.split(":"))
        dep = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if dep < now:
            dep += datetime.timedelta(days=1)
        dep_ts = int(dep.timestamp())
    except Exception:
        dep_ts = "now"

    url = (
        f"https://maps.googleapis.com/maps/api/directions/json"
        f"?origin={urllib.parse.quote(start_addr)}"
        f"&destination={urllib.parse.quote(end_addr)}"
        f"&mode={mode}&departure_time={dep_ts}&key={api_key}"
    )
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "OK" and data.get("routes"):
                route = data["routes"][0]["legs"][0]
                dur_val = route.get("duration_in_traffic", route.get("duration"))["value"]
                dist_val = route["distance"]["value"]
                return dur_val / 60.0, dist_val / 1000.0
    except Exception:
        pass
    return 0.0, 0.0

# ─────────────────────────────────────────────
# CALCOLO SCENARI
# ─────────────────────────────────────────────

def compute_scenarios(prof: dict, transp: dict, food: dict, s_rem: dict) -> list:
    """
    Genera tutti gli scenari possibili (da 0 a N giorni smart/settimana).
    Per ciascuno calcola bilancio annuale, ore di pendolarismo e kg CO2.
    """
    sett_w       = prof["work_days"]
    weeks        = s_rem.get("settimane_anno", 48)
    energia      = s_rem.get("energia", 0.85)
    pranzo_casa  = s_rem.get("pranzo_casa", 5.50)
    ticket_val   = food.get("ticket", 0.0)
    ticket_mode  = food.get("ticket_mode", "Solo giorni in presenza")
    coffee       = food.get("coffee", 0.0)
    lunch        = food.get("lunch", 0.0)
    parking_day  = transp.get("parking_cost", 0.0)
    toll_day     = transp.get("toll_cost", 0.0)

    scenarios = []
    for smart in range(sett_w + 1):
        presence      = sett_w - smart
        t_cost_w      = transp.get("total_cost", 0.0) * 2 * presence
        t_time_w      = (transp.get("total_duration", 0.0) * 2 / 60) * presence
        t_co2_w       = transp.get("total_co2", 0.0) * 2 * presence
        park_w        = parking_day * presence
        toll_w        = toll_day * 2 * presence          # A/R
        food_uff_w    = (coffee + lunch) * presence
        energia_w     = energia * smart
        remote_food_w = pranzo_casa * smart

        if ticket_mode == "Solo giorni in presenza":
            ticket_recv_w = ticket_val * presence
        elif ticket_mode == "Solo giorni in smart working":
            ticket_recv_w = ticket_val * smart
        else:
            ticket_recv_w = ticket_val * sett_w

        uscite_w   = t_cost_w + park_w + toll_w + food_uff_w + energia_w + remote_food_w
        entrate_w  = ticket_recv_w
        cost_net_w = entrate_w - uscite_w

        scenarios.append({
            "smart":           smart,
            "presence":        presence,
            "bilancio":        cost_net_w * weeks,
            "time":            t_time_w * weeks,
            "co2":             t_co2_w * weeks,
            "_t_cost_w":       t_cost_w,
            "_park_w":         park_w,
            "_toll_w":         toll_w,
            "_food_uff_w":     food_uff_w,
            "_energia_w":      energia_w,
            "_remote_food_w":  remote_food_w,
            "_ticket_recv_w":  ticket_recv_w,
        })
    return scenarios

# ─────────────────────────────────────────────
# RIEPILOGO COSTI HTML
# ─────────────────────────────────────────────

def build_summary_html(scenario: dict, s_rem: dict) -> str:
    """Genera la tabella HTML di riepilogo costi settimanali e annuali per uno scenario."""
    weeks   = s_rem.get("settimane_anno", 48)
    smart   = scenario["smart"]
    presence = scenario["presence"]

    rows_uscite = [
        ("🚗 Trasporto (A/R)",        scenario["_t_cost_w"]),
        ("🅿️ Parcheggio",             scenario["_park_w"]),
        ("🛣️ Pedaggio",               scenario["_toll_w"]),
        ("🍽️ Ristorazione (Ufficio)", scenario["_food_uff_w"]),
        ("💡 Extra utenze (Remoto)",  scenario["_energia_w"]),
        ("🥗 Pranzo a casa (Remoto)", scenario["_remote_food_w"]),
    ]
    rows_entrate = [("🎫 Buoni pasto ricevuti", scenario["_ticket_recv_w"])]

    tot_uscite  = sum(v for _, v in rows_uscite)
    tot_entrate = sum(v for _, v in rows_entrate)

    html  = f"<h4>📋 Riepilogo scenario: <b>{smart} gg smart / {presence} gg presenza</b></h4>"
    html += (
        "<table width='100%'>"
        "<tr><th style='text-align:left;'>Voce</th>"
        "<th style='text-align:center;'>Settimanale</th>"
        "<th style='text-align:center;'>Annuale</th></tr>"
    )
    for label, v in rows_uscite:
        html += (
            f"<tr><td style='text-align:left;'>{label}</td>"
            f"<td style='text-align:center;'>{format_euro(v)}</td>"
            f"<td style='text-align:center;'>{format_euro(v * weeks)}</td></tr>"
        )
    html += (
        f"<tr><td style='text-align:left;'><b>Totale uscite</b></td>"
        f"<td style='text-align:center;'><b>{format_euro(tot_uscite)}</b></td>"
        f"<td style='text-align:center;'><b>{format_euro(tot_uscite * weeks)}</b></td></tr>"
    )
    for label, v in rows_entrate:
        html += (
            f"<tr><td style='text-align:left;'>{label}</td>"
            f"<td style='text-align:center;'>{format_euro(v)}</td>"
            f"<td style='text-align:center;'>{format_euro(v * weeks)}</td></tr>"
        )
    saldo_w   = tot_entrate - tot_uscite
    saldo_ann = saldo_w * weeks
    color     = "#27ae60" if saldo_w >= 0 else "#c0392b"
    html += (
        f"<tr><td style='text-align:left;'><b>Saldo netto</b></td>"
        f"<td style='text-align:center;color:{color};'><b>{format_euro(saldo_w)}</b></td>"
        f"<td style='text-align:center;color:{color};'><b>{format_euro(saldo_ann)}</b></td></tr>"
        f"</table><br>"
    )
    return html

# ─────────────────────────────────────────────
# OUTPUT DETERMINISTICI — ANALISI SCENARI
# ─────────────────────────────────────────────

def build_insights_html(
    prof: dict,
    optimal_smart: int,
    allowed: int,
    worst,
    allowed_sc,
    optimal,
    mai_positivo: bool,
) -> str:
    """
    Genera il pannello HTML degli insight deterministici.
    Confronta lo scenario attuale, quello ottimale e il risparmio potenziale.
    Il parametro df rimosso in quanto non utilizzato nel corpo.
    """
    time_allowed = round(worst["time"] - allowed_sc["time"], 1)
    co2_allowed  = round(worst["co2"]  - allowed_sc["co2"],  1)
    time_optimal = round(worst["time"] - optimal["time"],    1)
    co2_optimal  = round(worst["co2"]  - optimal["co2"],     1)
    delta_time   = round(time_optimal - time_allowed, 1)
    delta_co2    = round(co2_optimal  - co2_allowed,  1)
    weekly_hours = prof.get("weekly_hours", 40)
    weeks_eq     = round(time_optimal / weekly_hours, 1) if time_optimal > 0 else 0

    score = prof.get("remote_index",   0)
    cls   = prof.get("classification", "")
    expl  = prof.get("explanation",    "")

    be_label = "Configurazione di minor costo"
    be_icon  = "⚠️" if mai_positivo else "📍"
    be_desc  = (
        " — nessun bilancio positivo raggiungibile con i costi attuali"
        if mai_positivo else
        " — da questo punto lo smart working genera risparmio netto"
    )

    rows = [
        (be_icon, f"<b>{be_label} ({optimal_smart} gg/sett):</b>{be_desc}"),
        ("📊",    f"<b>Scenario attuale ({allowed} gg/sett):</b> "
                  f"{time_allowed} ore risparmiate/anno · {co2_allowed} kg CO₂ evitati/anno"),
        ("📈",    f"<b>Scenario a minor costo ({optimal_smart} gg/sett):</b> "
                  f"{time_optimal} ore risparmiate/anno · {co2_optimal} kg CO₂ evitati/anno"),
        ("➕",    f"<b>Potenziale aggiuntivo</b> (attuale → minor costo): "
                  f"+{delta_time} ore/anno · +{delta_co2} kg CO₂/anno"),
        ("🧠",   f"<b>Remotizzabilità:</b> {score}/100 — {cls}. {expl}"),
    ]
    if weeks_eq > 0:
        rows.append((
            "⏱️",
            f"<b>Equivalente temporale:</b> nello scenario ottimale risparmieresti "
            f"<b>{weeks_eq} settimane lavorative</b> di pendolarismo all'anno",
        ))

    html = "<div style='margin-top:16px;'>"
    for icon, text in rows:
        html += (
            f"<div style='display:flex;gap:10px;padding:10px 0;"
            f"border-bottom:1px solid #eee;align-items:flex-start;'>"
            f"<span style='font-size:1.2em;'>{icon}</span>"
            f"<span style='line-height:1.5;'>{text}</span>"
            f"</div>"
        )
    html += "</div>"
    return html

# ─────────────────────────────────────────────
# CALLBACK UI
# ─────────────────────────────────────────────

def update_status(st_dict):
    """Aggiorna il testo di stato della sezione in sidebar."""
    return "✅ Completa" if st_dict else "❌ Incompleta"

def toggle_auto_fields(vehicle: str):
    """
    Gestisce parcheggio E pedaggio: visibili solo per AUTO.
    Quando si cambia a mezzo non-auto, azzera entrambi i campi.
    Ritorna 3 update: parcheggio_number, pedaggio_radio, pedaggio_number.
    """
    is_auto = vehicle in AUTO_TYPES
    if is_auto:
        return (
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=False),  # pedaggio_val resta nascosto finché radio = Sì
        )
    return (
        gr.update(visible=False, value=0.0),
        gr.update(visible=False, value="No"),
        gr.update(visible=False, value=0.0),
    )

def toggle_toll_value(yn: str):
    """Mostra/nasconde il campo valore pedaggio in base al radio Sì/No."""
    return gr.update(visible=(yn == "Sì"), value=0.0 if yn == "No" else gr.update())

def update_visibility(n):
    """Mostra/nasconde i gruppi tratta in base al numero selezionato."""
    return [gr.update(visible=(i < n)) for i in range(4)]

def fmt_choices(query):
    """Geocodifica un indirizzo e restituisce choices (label, value) con coordinate embedded."""
    if not query or len(str(query).strip()) < 3:
        return gr.update(choices=[])
    if "###" in str(query):
        return gr.update()
    results = search_address_nominatim(query)
    if not results:
        return gr.update(choices=[])
    choices = [
        (r["display_name"], f"{r['display_name']}###{r['lat']}###{r['lon']}")
        for r in results
    ]
    return gr.update(choices=choices, value=choices[0][1])

# ─────────────────────────────────────────────
# LOGICA INDICE DI REMOTIZZABILITÀ
# ─────────────────────────────────────────────

WEIGHTS = {
    "digital":  0.30,
    "autonomy": 0.20,
    "presence": 0.20,
    "hardware": 0.15,
    "sync":     0.15,
}

def compute_remote_index(digital: float, autonomy: float, presence: float, hardware: float, sync: float) -> float:
    """Calcola l'indice di remotizzabilità (0-100) come media pesata dei driver."""
    score = (
        WEIGHTS["digital"]  * digital
        + WEIGHTS["autonomy"]  * autonomy
        + WEIGHTS["presence"]  * (100 - presence)
        + WEIGHTS["hardware"]  * (100 - hardware)
        + WEIGHTS["sync"]      * (100 - sync)
    )
    return round(score, 1)

def classify_remote(score: float) -> str:
    """Classifica l'indice di remotizzabilità in tre fasce."""
    if score >= 75:
        return "🟢 Alta remotizzabilità"
    elif score >= 50:
        return "🟡 Remotizzabilità ibrida"
    else:
        return "🔴 Bassa remotizzabilità"

def explain_remote(score: float, digital, autonomy, presence, hardware, sync) -> str:
    """Genera una spiegazione testuale dei driver dominanti positivi e negativi."""
    positive, negative = [], []
    if digital  > 70: positive.append("alta digitalizzazione dei processi")
    if autonomy > 70: positive.append("elevata autonomia operativa")
    if presence > 70: negative.append("forte necessità di setup fisico")
    if hardware > 70: negative.append("dipendenza da infrastrutture fisiche")
    if sync     > 70: negative.append("alta sincronia collaborativa richiesta")
    parts = []
    if positive: parts.append("Fattori favorevoli: " + ", ".join(positive))
    if negative: parts.append("Fattori limitanti: "  + ", ".join(negative))
    if not parts: parts.append("Nessun driver dominante — profilo bilanciato")
    return ". ".join(parts) + "."

def build_profile_card(score: float) -> str:
    """Genera la card HTML con barra di avanzamento per l'indice di remotizzabilità."""
    cls   = classify_remote(score)
    color = "#27ae60" if score >= 75 else ("#f39c12" if score >= 50 else "#c0392b")
    bar_w = int(score)
    return (
        f"<div style='border:1px solid #ddd;border-radius:8px;padding:14px 18px;"
        f"background:#fafafa;margin-top:10px;'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
        f"<span style='font-size:1.1em;font-weight:bold;'>{cls}</span>"
        f"<span style='font-size:1.4em;font-weight:bold;color:{color};'>{score}/100</span>"
        f"</div>"
        f"<div style='background:#e0e0e0;border-radius:4px;height:10px;margin:10px 0;'>"
        f"<div style='background:{color};width:{bar_w}%;height:10px;border-radius:4px;'></div>"
        f"</div>"
        f"</div>"
    )

# ─────────────────────────────────────────────
# SALVATAGGIO PROFILO
# ─────────────────────────────────────────────

def save_profile(w_d, p_a, h_w, wk, dig, aut, inter, pres, sync):
    """Calcola l'indice di remotizzabilità e salva il profilo lavorativo nello State."""
    score       = compute_remote_index(dig, aut, inter, pres, sync)
    cls         = classify_remote(score)
    explanation = explain_remote(score, dig, aut, inter, pres, sync)
    data = {
        "work_days":      int(w_d),
        "policy_allowed": int(p_a),
        "week_year":      int(wk),
        "weekly_hours":   float(h_w),
        "remote_index":   score,
        "classification": cls,
        "explanation":    explanation,
    }
    card = build_profile_card(score)
    md   = f"**{cls}** — Indice: **{score}/100**\n\n_{explanation}_"
    return data, md, card

# ─────────────────────────────────────────────
# CALCOLO SPOSTAMENTI E TRASPORTI
# ─────────────────────────────────────────────

def calc_transport(n, df_t, api_choice, gmaps_key, dep_time, *args):
    """
    Calcola costi, emissioni e durata degli spostamenti casa-lavoro.
    args layout per tratta (6 elementi × max 4 tratte):
        start, end, vehicle, parking, toll_yn, toll_val
    """
    total_time = total_dist = total_cost = total_co2 = total_parking = total_toll = 0.0

    for i in range(int(n)):
        idx      = i * 6
        start    = args[idx]
        end      = args[idx + 1]
        vehicle  = args[idx + 2]
        parking  = float(args[idx + 3] or 0)
        toll_yn  = args[idx + 4]
        toll_val = float(args[idx + 5] or 0)

        if not start or not end:
            return gr.update(), "⚠️ Seleziona gli indirizzi."

        def extract_coords(val):
            """
            Estrae (lat, lon) dal formato 'label###lat###lon'.
            Se il valore non ha coordinate embedded, ri-geocodifica come fallback.
            """
            val   = str(val).strip()
            parts = val.split("###")
            if len(parts) == 3:
                try:
                    return float(parts[1]), float(parts[2])
                except ValueError:
                    pass
            res = search_address_nominatim(val)
            if res:
                return float(res[0]["lat"]), float(res[0]["lon"])
            return None, None

        def clean_addr_str(val):
            """Restituisce la parte testuale leggibile, rimuovendo ###lat###lon."""
            val = str(val).strip()
            return val.split("###")[0].strip() if "###" in val else val

        if api_choice == "OpenStreetMap":
            lat1, lon1 = extract_coords(start)
            lat2, lon2 = extract_coords(end)
            if lat1 is None or lat2 is None:
                return gr.update(), "⚠️ Indirizzo non trovato. Riprova a digitare e selezionare un risultato."
            dur, dist = get_route_osm(lat1, lon1, lat2, lon2, vehicle)
        else:
            if not gmaps_key:
                return gr.update(), "⚠️ Inserisci la API Key di Google Maps."
            # Google Maps richiede la stringa leggibile, non le coordinate
            dur, dist = get_route_gmaps(
                clean_addr_str(start), clean_addr_str(end), vehicle, gmaps_key, dep_time
            )

        r_df     = df_t.loc[df_t["Mezzo"] == vehicle]
        cost_val = float(r_df["Costo"].iloc[0])     if not r_df.empty else 0.0
        co2_km   = float(r_df["CO2_km"].iloc[0])    if not r_df.empty else 0.0
        natura   = str(r_df["Unita_Costo"].iloc[0]).lower() if not r_df.empty else "km"

        if "min" in natura or vehicle == "Trasporto Pubblico":
            tickets  = math.ceil(dur / 100.0) if dur > 0 else 0
            if tickets == 0 and dist > 0:
                tickets = 1
            leg_cost = cost_val * tickets
        else:
            leg_cost = dist * cost_val

        total_time    += dur
        total_dist    += dist
        total_cost    += leg_cost
        total_co2     += dist * co2_km / 1000
        total_parking += parking
        total_toll    += toll_val if toll_yn == "Sì" else 0.0

    mm, ss = int(total_time), int((total_time * 60) % 60)
    data = {
        "total_duration": total_time,
        "total_cost":     total_cost,
        "total_co2":      total_co2,
        "parking_cost":   total_parking,
        "toll_cost":      total_toll,
    }
    msg = (
        f"✅ Dati sezione 'Spostamenti' salvati. Distanza: {total_dist:.1f} km - "
        f"Costo andata: {total_cost:.2f} € - "
        f"Parcheggio: {total_parking:.2f} €/giorno - "
        f"Pedaggio A/R: {total_toll:.2f} €/giorno - "
        f"CO₂: {total_co2 * 1000:.0f} g - "
        f"Durata andata: {mm}m {ss:02d}s"
    )
    return data, msg

# ─────────────────────────────────────────────
# RISTORAZIONE
# ─────────────────────────────────────────────

def save_food(coff, lun, tk, tk_val, tk_mode):
    """Valida e salva i dati della sezione Ristorazione nello State."""
    if tk == "Sì" and (tk_val is None or tk_val <= 0):
        return gr.update(), "❌ Il valore del buono pasto deve essere maggiore di 0."
    return (
        {
            "coffee":      coff,
            "lunch":       lun,
            "ticket":      tk_val if tk == "Sì" else 0.0,
            "ticket_mode": tk_mode if tk == "Sì" else "Solo giorni in presenza",
        },
        "✅ Dati sezione 'Ristorazione' salvati.",
    )

def update_settings(df, wk, current_s_rem):
    """Aggiorna il dataframe dei trasporti e le settimane lavorative nei Parametri (default)."""
    updated = dict(current_s_rem)  # preserva energia e pranzo_casa
    updated["settimane_anno"] = int(wk)
    return df, updated, "✅ Dati sezione 'Parametri (default)' salvati."

# ─────────────────────────────────────────────
# RISULTATI (3 output: tabella, riepilogo, insights)
# ─────────────────────────────────────────────

def process_results(prof, transp, food, s_rem):
    """
    Punto di ingresso principale per il calcolo dei risultati.
    Genera tabella scenari, riepilogo costi e insights deterministici.
    Viene chiamato automaticamente ad ogni salvataggio di sezione.
    """
    if not prof or not transp or not food:
        empty = "<p>Compila le sezioni Profilo Lavorativo, Spostamenti e Ristorazione</p>"
        return empty, empty, empty

    scenarios = compute_scenarios(prof, transp, food, s_rem)
    df        = pd.DataFrame(scenarios)

    # Scenario ottimale: massimo bilancio (massimo risparmio o minima perdita)
    optimal_smart = int(df.loc[df["bilancio"].idxmax(), "smart"])

    # Break-even: primo scenario con bilancio positivo; se assente, scenario di minor perdita
    mai_positivo = not (df["bilancio"] > 0).any()
    positive_df  = df[df["bilancio"] > 0]

    if not positive_df.empty:
        break_even_row = positive_df.loc[positive_df["bilancio"].idxmin()]
        legenda_be     = "primo punto di risparmio netto"
    else:
        break_even_row = df.loc[df["bilancio"].idxmax()]
        legenda_be     = "configurazione con la minor perdita economica"

    break_even_smart    = int(break_even_row["smart"])
    costo_full_presence = df[df["smart"] == 0].iloc[0]["bilancio"]

    # Nota contestuale che spiega il segno del bilancio
    if mai_positivo:
        nota_bilancio = (
            "<div style='background:#e8f4fd;border-left:4px solid #3498db;"
            "padding:10px 14px;border-radius:4px;margin-bottom:12px;font-size:0.93em;'>"
            "📌 <b>Come leggere questa tabella:</b> il bilancio è sempre negativo perché "
            "lavorare comporta comunque dei costi (spostamenti, pasti, utenze). "
            "L'obiettivo non è azzerare i costi, ma <b>minimizzarli</b>. "
            "La colonna <i>Smart working vs full-presence</i> mostra il confronto progressivo di giornate di Smart Working "
            "rispetto al lavorare sempre in presenza."
            "</div>"
        )
    else:
        nota_bilancio = (
            "<div style='background:#e8f4fd;border-left:4px solid #3498db;"
            "padding:10px 14px;border-radius:4px;margin-bottom:12px;font-size:0.93em;'>"
            "📌 <b>Come leggere questa tabella:</b> il costo netto positivo indica che "
            "le entrate (es. buoni pasto) superano le uscite nette. "
            "La colonna <i>Smart working vs full-presence</i> mostra il confronto progressivo di giornate di Smart Working "
            "rispetto al lavorare sempre in presenza."
            "</div>"
        )

    # Tabella scenari
    html = nota_bilancio + (
        "<table width='100%' text-align='center'>"
        "<tr style='background:#f0f2f6'>"
        "<th style='text-align:left;'>Giorni Smart</th>"
        "<th style='text-align:center;'>Costo Netto Annuale (€)</th>"
        "<th style='text-align:center;'>Smart working vs full-presence (€)</th>"
        "<th style='text-align:center;'>Tempo Pendolarismo Ann. (Ore)</th>"
        "<th style='text-align:center;'>Emissioni (Kg CO₂)</th>"
        "</tr>"
    )

    allowed = prof.get("policy_allowed", 0)
    for _, s in df.iterrows():
        is_be      = (int(s["smart"]) == break_even_smart)
        is_current = (int(s["smart"]) == allowed)

        if is_be:
            bg = "background:#e8f5e9;"
        elif is_current:
            bg = "background:#e8f3ff;"
        else:
            bg = ""

        risparmio      = s["bilancio"] - costo_full_presence
        risparmio_html = format_html_delta(risparmio)

        html += (
            f"<tr style='border-bottom:1px solid #ddd;{bg}'>"
            f"<td style='text-align:left;'><b>{int(s['smart'])}</b></td>"
            f"<td style='text-align:center;'>{format_html_delta(s['bilancio'])}</td>"
            f"<td style='text-align:center;'>{risparmio_html}</td>"
            f"<td style='text-align:center;'>{format_num(s['time'])}</td>"
            f"<td style='text-align:center;'>{format_num(s['co2'])}</td>"
            f"</tr>"
        )
    html += "</table><br>"

    # Legenda colori
    html += (
        "<p style='font-size:0.88em;color:#555;display:flex;align-items:center;gap:6px;'>"
        "<span style='display:inline-block;width:18px;height:14px;"
        "background:#e8f5e9;border:1px solid #b2dfdb;border-radius:3px;'></span>"
        f" {legenda_be} &nbsp;|&nbsp; "
        "<span style='display:inline-block;width:18px;height:14px;"
        "background:#e8f3ff;border:1px solid #bbdefb;border-radius:3px;'></span>"
        " scenario attuale del dipendente"
        "</p>"
    )

    # Riepilogo costi per lo scenario risparmio / minor perdita
    ref_row = df[df["smart"] == break_even_smart].iloc[0]
    summary = build_summary_html(ref_row, s_rem)

    # Insights deterministici
    worst               = df[df["smart"] == 0].iloc[0]
    allowed_sc          = df[df["smart"] == min(allowed, len(df) - 1)].iloc[0]
    be_row_for_insights = df[df["smart"] == break_even_smart].iloc[0]

    insights = build_insights_html(
        prof          = prof,
        optimal_smart = break_even_smart,
        allowed       = allowed,
        worst         = worst,
        allowed_sc    = allowed_sc,
        optimal       = be_row_for_insights,
        mai_positivo  = mai_positivo,
    )

    return html, summary, insights

# ─────────────────────────────────────────────
# INTERFACCIA GRADIO
# ─────────────────────────────────────────────

# Risoluzione del percorso base per il logo (compatibile con Colab e HF Spaces)
try:
    _base_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _base_dir = os.getcwd()

_logo_paths = [
    os.path.join(_base_dir, "logo.png"),
    "/content/logo.png",
    "logo.png",
]
_logo = next((_p for _p in _logo_paths if os.path.exists(_p)), None)

with gr.Blocks(title="Smart Working Dashboard") as demo:
    profile_state           = gr.State({})
    transport_state         = gr.State({})
    food_state              = gr.State({})
    settings_transport_state = gr.State(DEFAULT_TRANSPORT_DF)
    settings_remote_state   = gr.State(DEFAULT_REMOTE_COSTS.copy())

    gr.Markdown("# Smart Working Dashboard")

    # Output dichiarati con render=False per essere accessibili da tutti i tab
    results_table = gr.HTML("<p>Completa tutto per i risultati</p>", render=False)
    summary_out   = gr.HTML("<p>Dati non disponibili</p>",           render=False)
    insights_out  = gr.HTML("<p>Dati non disponibili</p>",           render=False)

    with gr.Row():

        # ── SIDEBAR ──────────────────────────────────────────────────────────
        with gr.Column(scale=1, min_width=250):
            if _logo:
                gr.Image(value=_logo, label="", show_label=False,
                         show_download_button=False, container=False, height=200)

            gr.Markdown("### Monitor Sezioni")
            st_p = gr.Textbox("❌ Incompleta", label="Profilo Lavorativo",      interactive=False)
            st_t = gr.Textbox("❌ Incompleta", label="Spostamenti e Trasporti", interactive=False)
            st_f = gr.Textbox("❌ Incompleta", label="Ristorazione",            interactive=False)
            profile_state.change(update_status, profile_state, st_p)
            transport_state.change(update_status, transport_state, st_t)
            food_state.change(update_status, food_state, st_f)

        # ── TABS ─────────────────────────────────────────────────────────────
        with gr.Column(scale=4):
            with gr.Tabs():

                # HOME
                with gr.Tab("🏠 Home"):
                    gr.Markdown("""
### Analisi dei Costi del Lavoro
Quantifica l'impatto reale del lavoro sul singolo dipendente su tre dimensioni: **economica**, **temporale** e **ambientale**.

#### ✨ Parametri considerati
- 👤 **Profilo Lavorativo** - Indice di remotizzabilità della mansione lavorativa
- 🚗 **Spostamenti** - Costi, tempi ed emissioni degli spostamenti (percorsi reali OSM/OSRM)
- ☕ **Ristorazione** - Pasti, break e buoni pasto configurabili per modalità di utilizzo
- ⚡ **Costi Remoto** - Costo giornaliero di lavoro in remoto (utenze, pasti)
- 📊 **Risultati** - Tabella scenari, riepilogo costi e insight (auto-aggiornamento)
- ⚙️ **Parametri (default)** - Tutti i parametri di calcolo personalizzabili e persistenti

#### 🔒 Privacy
I dati inseriti non vengono memorizzati. Le uniche chiamate esterne sono OpenStreetMap/Google Maps (geocoding).
""")
                    gr.HTML("""
<div style="
  background-color:#EAF4FB;
  border-left:6px solid #2E86C1;
  padding:15px;
  border-radius:8px;
  margin-top:12px;
  font-size:0.92em;
  line-height:1.6;
">
  <b>ℹ️ Nota metodologica</b><br><br>
  Questa analisi non intende esprimere un giudizio di valore sulla presenza in ufficio o sullo smart working.
  Entrambe le modalità hanno dimensioni relazionali, collaborative e organizzative che esulano da qualsiasi modello economico.<br><br>
  L'obiettivo è esclusivamente quello di <b>rendere visibili i costi nascosti del lavoro</b> — trasporto,
  parcheggio, ristorazione, utenze — che il dipendente sostiene indipendentemente dalla modalità scelta,
  e di identificare la configurazione che <b>minimizza l'impatto economico personale</b> nel rispetto della policy aziendale.
</div>
""")

                # PROFILO LAVORATIVO
                with gr.Tab("💼 Profilo Lavorativo"):
                    gr.Markdown(
                        "Muovi gli slider in base alla tua situazione reale. "
                        "I driver **positivi** (digital readiness, autonomia) aumentano l'indice; "
                        "i driver **limitanti** (setup fisico, hardware, sincronia) lo riducono."
                    )
                    with gr.Row():
                        w_d  = gr.Number(value=5, label="Giorni lavorativi a settimana")
                        p_a  = gr.Number(value=2, label="Giorni Smart Working a settimana")
                    with gr.Row():
                        h_w   = gr.Number(value=40, label="Ore lavorative settimanali (valori interi)")
                        wk_in = gr.Number(value=48, label="Settimane lavorative/anno")
                    with gr.Row():
                        with gr.Column():
                            d_i  = gr.Slider(0, 100, 50, label="Digital readiness",
                                             info="Attività gestibili tramite strumenti digitali")
                            a_i  = gr.Slider(0, 100, 50, label="Autonomia operativa",
                                             info="Capacità di lavorare senza supervisione continua")
                            in_i = gr.Slider(0, 100, 50, label="Allineamento in presenza",
                                             info="Necessità di incontri fisici e momenti decisionali")
                        with gr.Column():
                            pr_i = gr.Slider(0, 100, 50, label="Dipendenza hardware",
                                             info="Uso di macchinari o ambienti disponibili solo in sede")
                            sy_i = gr.Slider(0, 100, 50, label="Sincronia collaborativa",
                                             info="Necessità di interazioni in tempo reale")
                    s_p = gr.Button("Salva Dati 'Profilo Lavorativo'")
                    with gr.Row():
                        p_o   = gr.Markdown()
                        p_card = gr.HTML()

                    s_p.click(
                        save_profile,
                        [w_d, p_a, h_w, wk_in, d_i, a_i, in_i, pr_i, sy_i],
                        [profile_state, p_o, p_card]
                    ).then(
                        process_results,
                        [profile_state, transport_state, food_state, settings_remote_state],
                        [results_table, summary_out, insights_out]
                    )

                # SPOSTAMENTI
                with gr.Tab("🗺️ Spostamenti"):
                    api_choice = gr.Radio(
                        ["OpenStreetMap", "Google Maps"],
                        value="OpenStreetMap",
                        label="Provider Mappe (Calcolo Percorso)"
                    )
                    gmaps_key = gr.Textbox(visible=False, label="Google Maps API Key", type="password")
                    dep_time  = gr.Textbox(visible=False, label="Orario partenza (HH:MM)", value="08:00")
                    api_choice.change(
                        lambda x: [gr.update(visible=x == "Google Maps"), gr.update(visible=x == "Google Maps")],
                        inputs=api_choice,
                        outputs=[gmaps_key, dep_time]
                    )
                    gr.HTML("""
<div style="
  background-color:#FFF8E1;
  border-left:5px solid #F9A825;
  padding:12px 16px;
  border-radius:6px;
  margin:10px 0 14px 0;
  font-size:0.91em;
  line-height:1.6;
">
  <b>ℹ️ Differenza tra i provider di routing</b><br><br>
  <b>🗺️ OpenStreetMap (OSRM)</b> — gratuito, nessuna API key richiesta.
  Calcola il percorso ottimale sulla rete stradale aperta, senza tenere conto del traffico in tempo reale.
  Ideale per una stima rapida di distanza e durata nelle condizioni di traffico standard.<br><br>
  <b>🌐 Google Maps</b> — richiede una API key personale (Google Cloud Console, piano a consumo).
  Utilizza dati di traffico storici e in tempo reale, con supporto al <b>Trasporto Pubblico</b>
  e alla possibilità di impostare un <b>orario di partenza</b> specifico per una stima più attendibile
  nei percorsi pendolari (es. ora di punta).
</div>
""")

                    n_l = gr.Slider(1, 4, 1, step=1, label="N° Tratte (solo andata)")
                    l_g, l_i = [], []

                    for i in range(4):
                        with gr.Group(visible=(i == 0)) as g:
                            gr.Markdown(f"**Tratta n.{i+1}**")
                            with gr.Row():
                                start_field = gr.Dropdown(
                                    label="Partenza", choices=[], allow_custom_value=True,
                                    info="Digita l'indirizzo e attendi i suggerimenti")
                                end_field = gr.Dropdown(
                                    label="Arrivo", choices=[], allow_custom_value=True,
                                    info="Digita l'indirizzo e attendi i suggerimenti")

                            start_field.change(fn=fmt_choices, inputs=start_field, outputs=start_field)
                            end_field.change(fn=fmt_choices, inputs=end_field,   outputs=end_field)

                            v = gr.Dropdown(
                                choices=DEFAULT_TRANSPORT_DF["Mezzo"].tolist(),
                                value="Auto benzina",
                                label="Mezzo"
                            )
                            p = gr.Number(label="🅿️ Parcheggio/giorno (€)", value=0.0)

                            with gr.Row():
                                toll_yn  = gr.Radio(["No", "Sì"], value="No",
                                                    label="🛣️ Pedaggio autostradale?", visible=True)
                                toll_val = gr.Number(label="Costo pedaggio A/R (€/giorno)",
                                                     value=0.0, visible=False)

                            toll_yn.change(fn=toggle_toll_value, inputs=toll_yn, outputs=toll_val)
                            v.change(fn=toggle_auto_fields, inputs=v, outputs=[p, toll_yn, toll_val])

                        l_g.append(g)
                        l_i.extend([start_field, end_field, v, p, toll_yn, toll_val])  # 6 elementi per tratta

                    n_l.change(update_visibility, n_l, l_g)
                    c_t = gr.Button("Salva Dati 'Spostamenti'")
                    t_o = gr.Markdown()

                    c_t.click(
                        calc_transport,
                        [n_l, settings_transport_state, api_choice, gmaps_key, dep_time] + l_i,
                        [transport_state, t_o]
                    ).then(
                        process_results,
                        [profile_state, transport_state, food_state, settings_remote_state],
                        [results_table, summary_out, insights_out]
                    )

                # RISTORAZIONE
                with gr.Tab("🍽️ Ristorazione"):
                    c_in  = gr.Number(value=0.0, label="Break (bar, distributori, etc.) (€)")
                    l_in  = gr.Number(value=0.0, label="Pausa Pranzo (€)")
                    tk_in = gr.Radio(["No", "Sì"], value="No", label="Buoni pasto?")
                    tk_v  = gr.Number(value=0.0, visible=False, label="Valore buoni pasto")
                    tk_m  = gr.Radio(TICKET_MODES, value="Solo giorni in presenza",
                                     visible=False, label="Assegnati per:")
                    tk_in.change(
                        lambda x: [gr.update(visible=x == "Sì"), gr.update(visible=x == "Sì")],
                        tk_in, [tk_v, tk_m]
                    )
                    f_b = gr.Button("Salva Dati 'Ristorazione'")
                    f_o = gr.Markdown()

                    f_b.click(
                        save_food, [c_in, l_in, tk_in, tk_v, tk_m], [food_state, f_o]
                    ).then(
                        process_results,
                        [profile_state, transport_state, food_state, settings_remote_state],
                        [results_table, summary_out, insights_out]
                    )

                # COSTI REMOTO
                with gr.Tab("🌍 Costi Remoto"):
                    gr.Markdown(
                        "### 🏠 Costi Giornalieri in Remoto\n"
                        "Specifica i costi che sostieni nelle giornate in cui lavori da casa."
                    )
                    with gr.Row():
                        e_in_remote  = gr.Number(value=0.85, label="💡 Extra utenze (€/giorno)",
                                                 info="Aumento stimato di luce, riscaldamento/raffrescamento")
                        pr_in_remote = gr.Number(value=5.50, label="🥗 Pasto a casa (€/giorno)",
                                                 info="Costo medio del pranzo preparato in casa")
                    remote_save_btn = gr.Button("Salva Dati 'Costi Remoto'", variant="secondary")
                    remote_save_out = gr.Markdown()

                    def save_remote_costs(en, pr, current_s_rem):
                        """Aggiorna i costi del lavoro da remoto nello State."""
                        updated = dict(current_s_rem)
                        updated["energia"]     = float(en)
                        updated["pranzo_casa"] = float(pr)
                        return updated, "✅ Dati sezione 'Costi Remoto' salvati."

                    remote_save_btn.click(
                        save_remote_costs,
                        [e_in_remote, pr_in_remote, settings_remote_state],
                        [settings_remote_state, remote_save_out]
                    ).then(
                        process_results,
                        [profile_state, transport_state, food_state, settings_remote_state],
                        [results_table, summary_out, insights_out]
                    )

                # RISULTATI
                with gr.Tab("📈 Risultati"):
                    results_table.render()
                    summary_out.render()
                    gr.Markdown("### 📈 Analisi degli Scenari")
                    insights_out.render()

                # PARAMETRI
                with gr.Tab("⚙️ Parametri (default)"):
                    s_t_i = gr.Dataframe(value=DEFAULT_TRANSPORT_DF, interactive=True,
                                         label="Costo_km (€/km) e CO2_km (g/km)")
                    s_b = gr.Button("Salva Dati 'Parametri (default)'")
                    s_o = gr.Markdown()

                    s_b.click(
                        update_settings,
                        [s_t_i, wk_in, settings_remote_state],
                        [settings_transport_state, settings_remote_state, s_o]
                    ).then(
                        process_results,
                        [profile_state, transport_state, food_state, settings_remote_state],
                        [results_table, summary_out, insights_out]
                    )

if __name__ == "__main__":
    demo.launch(debug=True, share=True)
