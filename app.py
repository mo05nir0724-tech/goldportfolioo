import os
import re
import requests
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Edelstahlportfolio", page_icon="🪙", layout="wide")

st.markdown("""
<style>
    button[data-baseweb="tab"] { font-size: 16px !important; padding-top: 15px !important; padding-bottom: 15px !important; }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 🔗 SICHERE DATENBANK & AUTH-VERBINDUNG
# ==========================================
if "supabase" not in st.session_state:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        st.session_state.supabase = create_client(url, key)
    except KeyError:
        st.error("⚠️ Schlüssel fehlen in Streamlit Secrets!")
        st.stop()

supabase = st.session_state.supabase

class PortfolioItem:
  def __init__(self, db_id, name, typ, gewicht_gramm, datum, kaufpreis, manueller_wert=0.0):
    self.id = db_id
    self.name = name
    self.typ = typ.upper()
    self.gewicht_gramm = float(gewicht_gramm)
    self.datum = datum
    self.kaufpreis = float(kaufpreis)
    self.manueller_wert = float(manueller_wert)

  def get_aktueller_wert(self, gold_preis, silber_preis):
    if self.typ == "GOLD": return self.gewicht_gramm * gold_preis
    elif self.typ == "SILBER": return self.gewicht_gramm * silber_preis
    return self.manueller_wert

class VerkaufsItem:
  def __init__(self, db_id, name, typ, gewicht_gramm, kaufdatum, kaufpreis, verkaufspreis, verkauf_datum):
    self.id = db_id
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
    if self.kaufpreis <= 0: return 0.0
    return (self.get_realisierter_gewinn() / self.kaufpreis) * 100


@st.cache_data(ttl=60)
def hole_live_kurse():
  gold, silber = 120.55, 1.79
  headers = {"User-Agent": "Mozilla/5.0"}
  try:
    r_g = requests.get("https://www.goldpreis.de/", headers=headers, timeout=4)
    m_g = re.search(r"1\s*Gramm[\s\S]*?(\d{1,3}(?:\.\d{3})*,\d{2})\s*EUR", r_g.text, re.IGNORECASE)
    if m_g: gold = float(m_g.group(1).replace(".", "").replace(",", "."))

    r_s = requests.get("https://www.goldpreis.de/silberpreis/", headers=headers, timeout=4)
    m_s = re.search(r"1\s*Gramm[\s\S]*?(\d{1,3}(?:\.\d{3})*,\d{2})\s*EUR", r_s.text, re.IGNORECASE)
    if m_s: silber = float(m_s.group(1).replace(".", "").replace(",", "."))
  except: pass
  return gold, silber

def lade_aktive():
    response = supabase.table("portfolio").select("*").execute()
    return [PortfolioItem(row["id"], row["name"], row["typ"], row["gewicht_gramm"], row["datum"], row["kaufpreis"], row["manueller_wert"]) for row in response.data]

def lade_verkaufte():
    response = supabase.table("verkaeufe").select("*").execute()
    return [VerkaufsItem(row["id"], row["name"], row["typ"], row["gewicht_gramm"], row["kaufdatum"], row["kaufpreis"], row["verkaufspreis"], row["verkauf_datum"]) for row in response.data]


def main():
  st.title("🪙 Edelstahlportfolio")

  # --- LOGIN / REGISTRIEREN LOGIK ---
  if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = ""

  if not st.session_state.logged_in:
    st.subheader("Sicherer Login")
    
    tab_login, tab_register = st.tabs(["🔒 Einloggen", "📝 Neues Konto"])
    
    with tab_login:
      with st.form("login_form"):
        eingabe_email = st.text_input("E-Mail Adresse").strip()
        eingabe_pw = st.text_input("Passwort", type="password")
        if st.form_submit_button("Einloggen", use_container_width=True):
          with st.spinner("Authentifizierung..."):
              try:
                  auth_response = supabase.auth.sign_in_with_password({"email": eingabe_email, "password": eingabe_pw})
                  st.session_state.logged_in = True
                  st.session_state.user_email = eingabe_email
                  st.rerun()
              except Exception as e:
                  # Falls die E-Mail noch nicht bestätigt wurde, wirft Supabase hier einen Fehler
                  if "Email not confirmed" in str(e):
                      st.error("Bitte bestätige zuerst deine E-Mail-Adresse über den Link in deinem Postfach!")
                  else:
                      st.error("Falsche E-Mail oder Passwort!")
            
    with tab_register:
      with st.form("register_form"):
        neu_email = st.text_input("E-Mail Adresse").strip()
        neu_pw = st.text_input("Sicheres Passwort", type="password")
        neu_pw_confirm = st.text_input("Passwort bestätigen", type="password")
        
        if st.form_submit_button("Konto erstellen", type="primary", use_container_width=True):
          with st.spinner("Erstelle Konto..."):
              if not neu_email or not neu_pw:
                st.error("Bitte fülle alle Felder aus.")
              elif neu_pw != neu_pw_confirm:
                st.error("Die Passwörter stimmen nicht überein.")
              elif len(neu_pw) < 6:
                st.error("Das Passwort muss mindestens 6 Zeichen lang sein.")
              else:
                try:
                  supabase.auth.sign_up({"email": neu_email, "password": neu_pw})
                  # E-Mail wurde versendet, Nutzer wird NICHT eingeloggt
                  st.success("✅ Fast geschafft! Wir haben dir einen Bestätigungslink gesendet. Bitte überprüfe dein E-Mail-Postfach (und den Spam-Ordner) und klicke auf den Link, bevor du dich einloggst.")
                except Exception as e:
                  st.error(f"Fehler bei Registrierung: {str(e)}")
    return


  # --- WENN EINGELOGGT: HAUPTAPPLIKATION ---
  user_email = st.session_state.user_email

  st.sidebar.header("⚙️ Einstellungen")
  st.sidebar.write("👤 **Konto:**")
  st.sidebar.write(f"*{user_email}*")
  if st.sidebar.button("🚪 Ausloggen", use_container_width=True):
    supabase.auth.sign_out()
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.rerun()
    
  st.sidebar.divider()
  protokoll_modus = st.sidebar.toggle("Nur Protokoll-Modus (Werte ausblenden)", value=False, key="proto_modus")
  st.sidebar.divider()
  st.sidebar.caption("🎨 Tippe oben rechts auf **(⋮) ➔ Settings ➔ Theme**, um Dark Mode einzustellen.")

  if "erfolgs_meldung" in st.session_state:
      st.success(st.session_state.erfolgs_meldung)
      del st.session_state.erfolgs_meldung

  gold_g, silber_g = hole_live_kurse()
  aktive_items = lade_aktive()
  verkaufte_items = lade_verkaufte()

  if not protokoll_modus:
      col1, col2 = st.columns(2)
      col1.metric("Live-Goldpreis", f"{gold_g:,.2f} €/g".replace(".", ","))
      col2.metric("Live-Silberpreis", f"{silber_g:,.2f} €/g".replace(".", ","))
      st.divider()

  tab_aktiv, tab_verkauft, tab_neu = st.tabs(["📦 Aktiv", "💰 Verkauft", "➕ Neu"])

  with tab_aktiv:
    gesamt_kauf = sum(i.kaufpreis for i in aktive_items)
    if not protokoll_modus:
        gesamt_wert = sum(i.get_aktueller_wert(gold_g, silber_g) for i in aktive_items)
        gesamt_bilanz = gesamt_wert - gesamt_kauf
        c1, c2, c3 = st.columns(3)
        c1.metric("Kaufwert", f"{gesamt_kauf:,.0f} €".replace(".", ","))
        c2.metric("Akt. Wert", f"{gesamt_wert:,.0f} €".replace(".", ","))
        c3.metric("Bilanz", f"{gesamt_bilanz:,.0f} €".replace(".", ","), delta=f"{(gesamt_bilanz/gesamt_kauf*100) if gesamt_kauf > 0 else 0:.1f} %")
    else:
        st.metric("Investierter Gesamtbetrag", f"{gesamt_kauf:,.0f} €".replace(".", ","))

    st.subheader("Bestand")
    if aktive_items:
      with st.expander("Eintrag verkaufen oder löschen", expanded=False):
        k_idx = st.selectbox("Welches Stück?", options=range(len(aktive_items)), format_func=lambda x: f"{aktive_items[x].name} ({aktive_items[x].gewicht_gramm}g {aktive_items[x].typ})")
        col_p, col_d = st.columns(2)
        verkaufspreis_input = col_p.number_input("Verkaufspreis (€)", min_value=0.0, value=300.0)
        verkauf_datum_input = col_d.text_input("Verkaufs-Datum", "12.09.2026")
        item_zu_verkaufen = aktive_items[k_idx]

        if st.button("💵 Als verkauft buchen", type="primary", use_container_width=True):
          with st.spinner("Buche Verkauf..."):
              supabase.table("verkaeufe").insert({
                  "name": item_zu_verkaufen.name, "typ": item_zu_verkaufen.typ,
                  "gewicht_gramm": item_zu_verkaufen.gewicht_gramm, "kaufdatum": item_zu_verkaufen.datum,
                  "kaufpreis": item_zu_verkaufen.kaufpreis, "verkaufspreis": verkaufspreis_input, 
                  "verkauf_datum": verkauf_datum_input
              }).execute()
              supabase.table("portfolio").delete().eq("id", item_zu_verkaufen.id).execute()
              st.session_state.erfolgs_meldung = "Erfolgreich als verkauft verbucht!"
              st.rerun()

        if st.button("🗑️ Löschen (ohne Verkauf)", use_container_width=True):
          with st.spinner("Lösche Eintrag..."):
              supabase.table("portfolio").delete().eq("id", item_zu_verkaufen.id).execute()
              st.session_state.erfolgs_meldung = "Eintrag gelöscht!"
              st.rerun()
          
      tab_daten = []
      for item in aktive_items:
        reihen_daten = {"Datum": item.datum, "Name": item.name, "Typ": item.typ, "Gewicht": f"{item.gewicht_gramm:.1f} g".replace(".", ","), "Kaufpreis": f"{item.kaufpreis:,.0f} €".replace(".", ",")}
        if not protokoll_modus:
            w = item.get_aktueller_wert(gold_g, silber_g)
            gv = w - item.kaufpreis
            reihen_daten["Aktuell"] = f"{w:,.0f} €".replace(".", ",")
            reihen_daten["G/V"] = f"{gv:+,.0f} €".replace(".", ",")
        tab_daten.append(reihen_daten)
      st.dataframe(tab_daten, use_container_width=True, hide_index=True)
    else:
      st.info("Du hast noch keine Artikel. Gehe zum Tab '➕ Neu'.")


  with tab_verkauft:
    gesamter_erloes = sum(i.verkaufspreis for i in verkaufte_items)
    if not protokoll_modus:
        realisierter_gesamt_gewinn = sum(i.get_realisierter_gewinn() for i in verkaufte_items)
        vc1, vc2 = st.columns(2)
        vc1.metric("Gesamterlöse", f"{gesamter_erloes:,.0f} €".replace(".", ","))
        vc2.metric("Realisierter Gewinn", f"{realisierter_gesamt_gewinn:+,.0f} €".replace(".", ","))
    else:
        st.metric("Gesamterlöse durch Verkäufe", f"{gesamter_erloes:,.0f} €".replace(".", ","))

    if verkaufte_items:
      with st.expander("Verkauf aus Historie löschen"):
        v_loesch_idx = st.selectbox("Welcher Eintrag?", options=range(len(verkaufte_items)), format_func=lambda x: f"{verkaufte_items[x].name} (Verkauf für: {verkaufte_items[x].verkaufspreis}€)")
        if st.button("🗑️ Historie bereinigen", use_container_width=True):
          with st.spinner("Bereinige..."):
              supabase.table("verkaeufe").delete().eq("id", verkaufte_items[v_loesch_idx].id).execute()
              st.session_state.erfolgs_meldung = "Eintrag aus Historie entfernt!"
              st.rerun()

      v_tab_daten = []
      for item in verkaufte_items:
        reihen_daten = {"Kauf": item.kaufdatum, "Verkauf": item.verkauf_datum, "Name": item.name, "Typ": item.typ, "Kaufpreis": f"{item.kaufpreis:,.0f} €".replace(".", ","), "Erlös": f"{item.verkaufspreis:,.0f} €".replace(".", ",")}
        if not protokoll_modus:
            rg = item.get_realisierter_gewinn()
            reihen_daten["Gewinn"] = f"{rg:+,.0f} €".replace(".", ",")
        v_tab_daten.append(reihen_daten)
      st.dataframe(v_tab_daten, use_container_width=True, hide_index=True)
    else:
      st.info("Keine Verkäufe vorhanden.")


  with tab_neu:
    if protokoll_modus:
        st.subheader("Neuen Bestand erfassen (Protokoll)")
        st.info("💡 Da du im Protokoll-Modus bist, kannst du den Kaufpreis auch einfach auf 0,00 € stehen lassen.")
    else:
        st.subheader("Was hast du gekauft?")
        
    with st.form("neuer_eintrag_hauptbereich"):
      s_name = st.text_input("Name", "Maple Leaf", placeholder="z.B. Krügerrand")
      s_typ = st.selectbox("Typ", ["GOLD", "SILBER", "MANUELL"])
      col_w1, col_w2 = st.columns([2, 1])
      s_gew = col_w1.number_input("Gewicht", min_value=0.0, value=1.0, step=0.1)
      s_einheit = col_w2.selectbox("Einheit", ["g", "oz", "kg"])
      col_d1, col_d2 = st.columns(2)
      s_dat = col_d1.text_input("Kaufdatum", "12.09.2026")
      s_kauf = col_d2.number_input("Kaufpreis (€)", min_value=0.0, value=0.0 if protokoll_modus else 200.0)
      s_manuell = st.number_input("Manueller Wert (€)", min_value=0.0) if s_typ == "MANUELL" else 0.0

      if st.form_submit_button("💾 Speichern & ins Portfolio aufnehmen", type="primary", use_container_width=True):
        with st.spinner("Speichere verschlüsselt in Datenbank..."):
            gewicht_in_g = s_gew * 31.1034768 if s_einheit == "oz" else (s_gew * 1000.0 if s_einheit == "kg" else s_gew)
                
            supabase.table("portfolio").insert({
                "name": s_name, "typ": s_typ,
                "gewicht_gramm": gewicht_in_g, "datum": s_dat,
                "kaufpreis": s_kauf, "manueller_wert": s_manuell
            }).execute()
            
            st.session_state.erfolgs_meldung = f"{s_name} gespeichert! (Im Tab 'Aktiv' zu sehen)"
            st.rerun()

if __name__ == "__main__":
  main()
