import csv
import os
import re
import requests
import json
import streamlit as st

# Name der Datei, in der die Passwörter sicher gespeichert werden
USER_FILE = "users.json"

st.set_page_config(
    page_title="Edelstahlportfolio", page_icon="🪙", layout="wide"
)

# --- Verstecktes CSS für ein besseres Handy-Gefühl (Abstände & Knöpfe) ---
st.markdown("""
<style>
    button[data-baseweb="tab"] {
        font-size: 16px !important;
        padding-top: 15px !important;
        padding-bottom: 15px !important;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 💾 HILFSFUNKTIONEN FÜR BENUTZERVERWALTUNG
# ==========================================
def lade_benutzer():
    if not os.path.exists(USER_FILE):
        return {}
    try:
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def speichere_benutzer(benutzer_dict):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(benutzer_dict, f)


# ==========================================


class PortfolioItem:
    def __init__(self, name, typ, gewicht_gramm, datum, kaufpreis, manueller_wert=0.0):
        self.name = name
        self.typ = typ.upper()
        self.gewicht_gramm = float(gewicht_gramm)
        self.datum = datum
        self.kaufpreis = float(kaufpreis)
        self.manueller_wert = float(manueller_wert)

    def get_aktueller_wert(self, gold_preis, silber_preis):
        if self.typ == "GOLD":
            return self.gewicht_gramm * gold_preis
        elif self.typ == "SILBER":
            return self.gewicht_gramm * silber_preis
        return self.manueller_wert


class VerkaufsItem:
    def __init__(self, name, typ, gewicht_gramm, kaufdatum, kaufpreis, verkaufspreis, verkauf_datum):
        self.name = name
        self.typ = typ.upper()
        self.gewicht_gramm = float(gewicht_gramm)
        self.kaufdatum = kaufdatum
        self.kaufpreis = float(kaufpreis)
        self.verkaufspreis = float(verkaufspreis)
        self.verkauf_datum = verkauf_datum

    def get_realisierter_gewinn(self):
        return self.verkaufspreis - self.kaufpreis

    def get_rendite(self):
        if self.kaufpreis <= 0:
            return 0.0
        return (self.get_realisierter_gewinn() / self.kaufpreis) * 100


@st.cache_data(ttl=60)
def hole_live_kurse():
    gold = 120.55
    silber = 1.79
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    try:
        r_g = requests.get("https://www.goldpreis.de/", headers=headers, timeout=4)
        m_g = re.search(r"1\s*Gramm[\s\S]*?(\d{1,3}(?:\.\d{3})*,\d{2})\s*EUR", r_g.text, re.IGNORECASE)
        if m_g: gold = float(m_g.group(1).replace(".", "").replace(",", "."))

        r_s = requests.get("https://www.goldpreis.de/silberpreis/", headers=headers, timeout=4)
        m_s = re.search(r"1\s*Gramm[\s\S]*?(\d{1,3}(?:\.\d{3})*,\d{2})\s*EUR", r_s.text, re.IGNORECASE)
        if m_s: silber = float(m_s.group(1).replace(".", "").replace(",", "."))
    except Exception:
        pass
    return gold, silber


def lade_daten(datei, ist_verkauf=False):
    items = []
    if not os.path.exists(datei): return items
    try:
        with open(datei, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            for row in reader:
                if ist_verkauf and len(row) >= 7:
                    items.append(VerkaufsItem(row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
                elif not ist_verkauf and len(row) >= 6:
                    items.append(PortfolioItem(row[0], row[1], row[2], row[3], row[4], row[5]))
    except Exception:
        pass
    return items


def speichere_daten(datei, items, ist_verkauf=False):
    try:
        with open(datei, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            for item in items:
                if ist_verkauf:
                    writer.writerow(
                        [item.name, item.typ, item.gewicht_gramm, item.kaufdatum, item.kaufpreis, item.verkaufspreis,
                         item.verkauf_datum])
                else:
                    writer.writerow(
                        [item.name, item.typ, item.gewicht_gramm, item.datum, item.kaufpreis, item.manueller_wert])
    except Exception:
        pass


def main():
    st.title("🪙 Edelstahlportfolio")

    # --- LOGIN / REGISTRIEREN LOGIK ---
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ""

    if not st.session_state.logged_in:
        st.subheader("Willkommen! Bitte einloggen oder Konto erstellen.")

        # Zwei Tabs: Login und Registrieren
        tab_login, tab_register = st.tabs(["🔒 Einloggen", "📝 Neues Konto"])

        with tab_login:
            with st.form("login_form"):
                # lower() macht den Namen kleingeschrieben, damit "Marc" und "marc" gleich sind
                eingabe_user = st.text_input("Benutzername").strip().lower()
                eingabe_pw = st.text_input("Passwort", type="password")
                submit_login = st.form_submit_button("Einloggen", use_container_width=True)

                if submit_login:
                    benutzer_daten = lade_benutzer()
                    if eingabe_user in benutzer_daten and benutzer_daten[eingabe_user] == eingabe_pw:
                        st.session_state.logged_in = True
                        st.session_state.username = eingabe_user
                        st.rerun()
                    else:
                        st.error("Falscher Benutzername oder Passwort!")

        with tab_register:
            with st.form("register_form"):
                neu_user = st.text_input("Gewünschter Benutzername").strip().lower()
                neu_pw = st.text_input("Dein Passwort", type="password")
                neu_pw_confirm = st.text_input("Passwort bestätigen", type="password")
                submit_register = st.form_submit_button("Konto erstellen", type="primary", use_container_width=True)

                if submit_register:
                    benutzer_daten = lade_benutzer()

                    if not neu_user or not neu_pw:
                        st.error("Bitte fülle alle Felder aus.")
                    elif neu_user in benutzer_daten:
                        st.error("Diesen Benutzernamen gibt es leider schon. Wähle einen anderen!")
                    elif neu_pw != neu_pw_confirm:
                        st.error("Die Passwörter stimmen nicht überein.")
                    elif len(neu_user) < 3:
                        st.error("Der Benutzername muss mindestens 3 Zeichen lang sein.")
                    else:
                        # Neuen Benutzer speichern
                        benutzer_daten[neu_user] = neu_pw
                        speichere_benutzer(benutzer_daten)
                        st.success("Konto erfolgreich erstellt! Du kannst dich jetzt unter 'Einloggen' anmelden.")

        return  # Stoppt hier, wenn nicht eingeloggt
    # --- ENDE LOGIN LOGIK ---

    # --- WENN EINGELOGGT: HAUPTAPPLIKATION ---
    username = st.session_state.username
    aktiv_datei = f"sammlung_{username}.csv"
    verkauft_datei = f"verkauft_{username}.csv"

    st.sidebar.write(f"Angemeldet als: **{username.capitalize()}**")
    if st.sidebar.button("🚪 Ausloggen", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

    gold_g, silber_g = hole_live_kurse()
    aktive_items = lade_daten(aktiv_datei, ist_verkauf=False)
    verkaufte_items = lade_daten(verkauft_datei, ist_verkauf=True)

    col1, col2 = st.columns(2)
    col1.metric("Live-Goldpreis", f"{gold_g:,.2f} €/g".replace(".", ","))
    col2.metric("Live-Silberpreis", f"{silber_g:,.2f} €/g".replace(".", ","))

    st.divider()

    tab_aktiv, tab_verkauft, tab_neu = st.tabs(
        ["📦 Aktiv", "💰 Verkauft", "➕ Neu"]
    )

    # --- TAB 1: AKTIVES PORTFOLIO ---
    with tab_aktiv:
        gesamt_kauf = sum(i.kaufpreis for i in aktive_items)
        gesamt_wert = sum(i.get_aktueller_wert(gold_g, silber_g) for i in aktive_items)
        gesamt_bilanz = gesamt_wert - gesamt_kauf

        c1, c2, c3 = st.columns(3)
        c1.metric("Kaufwert", f"{gesamt_kauf:,.0f} €".replace(".", ","))
        c2.metric("Akt. Wert", f"{gesamt_wert:,.0f} €".replace(".", ","))
        c3.metric(
            "Bilanz",
            f"{gesamt_bilanz:,.0f} €".replace(".", ","),
            delta=f"{(gesamt_bilanz / gesamt_kauf * 100) if gesamt_kauf > 0 else 0:.1f} %"
        )

        st.subheader("Aktionen")
        if aktive_items:
            with st.expander("Eintrag verkaufen oder löschen", expanded=False):
                k_idx = st.selectbox(
                    "Welches Stück?",
                    options=range(len(aktive_items)),
                    format_func=lambda
                        x: f"{aktive_items[x].name} ({aktive_items[x].gewicht_gramm}g {aktive_items[x].typ})"
                )
                col_p, col_d = st.columns(2)
                verkaufspreis_input = col_p.number_input("Verkaufspreis (€)", min_value=0.0, value=300.0)
                verkauf_datum_input = col_d.text_input("Datum", "12.09.2026")

                if st.button("💵 Als verkauft buchen", type="primary", use_container_width=True):
                    item_zu_verkaufen = aktive_items[k_idx]
                    verkauftes_item = VerkaufsItem(
                        name=item_zu_verkaufen.name, typ=item_zu_verkaufen.typ,
                        gewicht_gramm=item_zu_verkaufen.gewicht_gramm,
                        kaufdatum=item_zu_verkaufen.datum, kaufpreis=item_zu_verkaufen.kaufpreis,
                        verkaufspreis=verkaufspreis_input, verkauf_datum=verkauf_datum_input
                    )
                    verkaufte_items.append(verkauftes_item)
                    del aktive_items[k_idx]
                    speichere_daten(aktiv_datei, aktive_items, ist_verkauf=False)
                    speichere_daten(verkauft_datei, verkaufte_items, ist_verkauf=True)
                    st.success("Verkauft!")
                    st.rerun()

                if st.button("🗑️ Löschen (ohne Verkauf)", use_container_width=True):
                    del aktive_items[k_idx]
                    speichere_daten(aktiv_datei, aktive_items, ist_verkauf=False)
                    st.success("Gelöscht!")
                    st.rerun()

            tab_daten = []
            for idx, item in enumerate(aktive_items):
                w = item.get_aktueller_wert(gold_g, silber_g)
                gv = w - item.kaufpreis
                tab_daten.append({
                    "Name": item.name,
                    "Typ": item.typ,
                    "Gewicht": f"{item.gewicht_gramm:.1f}g".replace(".", ","),
                    "Kaufpreis": f"{item.kaufpreis:,.0f} €",
                    "Aktuell": f"{w:,.0f} €",
                    "G/V": f"{gv:+,.0f} €",
                })
            st.dataframe(tab_daten, use_container_width=True, hide_index=True)
        else:
            st.info("Du hast noch keine Artikel. Gehe zum Tab '➕ Neu'.")

    # --- TAB 2: VERKAUFT ---
    with tab_verkauft:
        realisierter_gesamt_gewinn = sum(i.get_realisierter_gewinn() for i in verkaufte_items)
        gesamter_erloes = sum(i.verkaufspreis for i in verkaufte_items)

        vc1, vc2 = st.columns(2)
        vc1.metric("Gesamterlöse", f"{gesamter_erloes:,.0f} €".replace(".", ","))
        vc2.metric("Realisierter Gewinn", f"{realisierter_gesamt_gewinn:+,.0f} €".replace(".", ","))

        if verkaufte_items:
            with st.expander("Verkauf aus Historie löschen"):
                v_loesch_idx = st.selectbox(
                    "Welcher Eintrag?",
                    options=range(len(verkaufte_items)),
                    format_func=lambda
                        x: f"{verkaufte_items[x].name} (Gewinn: {verkaufte_items[x].get_realisierter_gewinn()}€)"
                )
                if st.button("🗑️ Historie bereinigen", use_container_width=True):
                    del verkaufte_items[v_loesch_idx]
                    speichere_daten(verkauft_datei, verkaufte_items, ist_verkauf=True)
                    st.success("Aus Historie entfernt!")
                    st.rerun()

            v_tab_daten = []
            for idx, item in enumerate(verkaufte_items):
                rg = item.get_realisierter_gewinn()
                v_tab_daten.append({
                    "Name": item.name,
                    "Typ": item.typ,
                    "Kauf": f"{item.kaufpreis:,.0f} €",
                    "Verkauf": f"{item.verkaufspreis:,.0f} €",
                    "Gewinn": f"{rg:+,.0f} €",
                })
            st.dataframe(v_tab_daten, use_container_width=True, hide_index=True)
        else:
            st.info("Keine Verkäufe vorhanden.")

    # --- TAB 3: NEUER EINTRAG ---
    with tab_neu:
        st.subheader("Was hast du gekauft?")
        with st.form("neuer_eintrag_hauptbereich"):
            s_name = st.text_input("Name", "Maple Leaf", placeholder="z.B. Krügerrand")
            s_typ = st.selectbox("Typ", ["GOLD", "SILBER", "MANUELL"])

            col_w1, col_w2 = st.columns([2, 1])
            s_gew = col_w1.number_input("Gewicht", min_value=0.0, value=1.0, step=0.1)
            s_einheit = col_w2.selectbox("Einheit", ["g", "oz", "kg"])

            col_d1, col_d2 = st.columns(2)
            s_dat = col_d1.text_input("Kaufdatum", "12.09.2026")
            s_kauf = col_d2.number_input("Kaufpreis (€)", min_value=0.0, value=200.0)

            s_manuell = 0.0
            if s_typ == "MANUELL":
                s_manuell = st.number_input("Manueller Wert (€)", min_value=0.0)

            if st.form_submit_button("💾 Speichern & ins Portfolio aufnehmen", type="primary", use_container_width=True):
                gewicht_in_g = s_gew
                if s_einheit == "oz":
                    gewicht_in_g = s_gew * 31.1034768
                elif s_einheit == "kg":
                    gewicht_in_g = s_gew * 1000.0

                aktive_items.append(
                    PortfolioItem(s_name, s_typ, gewicht_in_g, s_dat, s_kauf, s_manuell)
                )
                speichere_daten(aktiv_datei, aktive_items, ist_verkauf=False)
                st.success(f"{s_name} gespeichert! Schau im Tab 'Aktiv' nach.")


if __name__ == "__main__":
    main()