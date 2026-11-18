import json
import os
import random
import time
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURAZIONE PAGINA E PERCORSI ---
st.set_page_config(
    page_title="iNaturalist TCG - Scimmie", page_icon="🐾", layout="centered"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(BASE_DIR, "scimmie.json")
TXT_FILE = os.path.join(BASE_DIR, "osservazioni.txt")

# --- 1.2 CONNESSIONE A GOOGLE SHEETS (GSPREAD) ---
def get_gspread_client():
    """Inizializza la connessione a Google Sheets usando i Secrets di Streamlit."""
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    secrets_dict = dict(st.secrets["connections"]["gsheets"])
    # Estrae il dizionario JSON dal blocco service_account_json dei secrets
    if "service_account_json" in secrets_dict:
        import json
        if isinstance(secrets_dict["service_account_json"], str):
            sa_info = json.loads(secrets_dict["service_account_json"])
        else:
            sa_info = secrets_dict["service_account_json"]
    else:
        sa_info = secrets_dict

    creds = Credentials.from_service_account_info(sa_info, scopes=scope)
    client = gspread.authorize(creds)
    return client

def load_all_cards_from_gsheets():
    """Carica tutte le carte salvate nel Foglio Google restituendo un DataFrame."""
    try:
        client = get_gspread_client()
        spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet = client.open_by_url(spreadsheet_url).worksheet("carte")
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=[
                "player_name", "common_name", "latin_name", "rarity", 
                "image_url", "place_guess", "user_login", "obs_id", "is_cover"
            ])
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame(columns=[
            "player_name", "common_name", "latin_name", "rarity", 
            "image_url", "place_guess", "user_login", "obs_id", "is_cover"
        ])

def save_card_to_gsheets(card_data, player_name):
    """Aggiunge una nuova carta in coda al Foglio Google in modo sicuro."""
    try:
        client = get_gspread_client()
        spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet = client.open_by_url(spreadsheet_url).worksheet("carte")
        row = [
            player_name,
            card_data["common_name"],
            card_data["latin_name"],
            card_data["rarity"],
            card_data["image_url"],
            card_data["place_guess"],
            card_data["user_login"],
            card_data["obs_id"],
            False
        ]
        sheet.append_row(row)
    except Exception as e:
        st.error(f"Errore di salvataggio su Cloud: {e}")

def update_cover_in_gsheets(player_name, common_name, selected_obs_id):
    """Aggiorna la copertina modificando le celle direttamente nel foglio."""
    try:
        client = get_gspread_client()
        spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet = client.open_by_url(spreadsheet_url).worksheet("carte")
        records = sheet.get_all_records()
        
        # Scorriamo le righe per trovare corrispondenze e aggiornare la colonna is_cover
        for idx, row in enumerate(records, start=2): # start=2 perché la riga 1 è l'intestazione
            if str(row.get("player_name")) == str(player_name) and str(row.get("common_name")) == str(common_name):
                is_target = str(row.get("obs_id")) == str(selected_obs_id)
                # Troviamo la colonna "is_cover" (assumendo sia la 9°)
                sheet.update_cell(idx, 9, is_target)
    except Exception as e:
        st.error(f"Errore durante l'aggiornamento della copertina: {e}")

# --- 1.5 SCHERMATA LOGIN / NOME UTENTE ---
if "player_name" not in st.session_state:
  if "user" in st.query_params:
    st.session_state.player_name = st.query_params["user"]
  else:
    st.session_state.player_name = None

if not st.session_state.player_name:
  st.markdown(
      """<div style='text-align: center; padding: 40px 20px; background: #427a4d; border-radius: 15px; color: white; font-family: Arial; margin-bottom: 20px;'>
<h2>🐾 Benvenuto in iNaturalist TCG!</h2>
<p style='font-size: 14px; margin-top: 10px;'>Inserisci il tuo nome per iniziare la collezione o ricaricare i tuoi progressi salvati.</p>
</div>""",
      unsafe_allow_html=True,
  )

  col1, col2, col3 = st.columns([1, 2, 1])
  with col2:
    username_input = st.text_input(
        "Il tuo Nome o Nickname:", placeholder="es. marco"
    )
    if st.button("Entra nel Gioco 🚀", use_container_width=True, type="primary"):
      if username_input.strip():
        clean_name = (
            username_input.strip().lower().replace(" ", "_").replace("/", "_")
        )
        st.session_state.player_name = clean_name
        st.query_params["user"] = clean_name
        st.rerun()
      else:
        st.error("Per favore, inserisci un nome valido!")
  st.stop()

current_user = st.session_state.player_name

if "species" in st.query_params:
  st.session_state.selected_species = st.query_params["species"]
  st.session_state.page = "species_detail"
  del st.query_params["species"]


# --- 2. CARICAMENTO DATI GIOCO ---
@st.cache_data
def load_game_data():
  species_data = []
  if os.path.exists(JSON_FILE):
    with open(JSON_FILE, "r", encoding="utf-8") as f:
      species_data = json.load(f)

  species_data_txt = {}
  if os.path.exists(TXT_FILE):
    with open(TXT_FILE, "r", encoding="utf-8", errors="ignore") as f:
      f.readline()
      for line in f:
        parts = line.strip().split("\t")
        if len(parts) >= 6:
          obs_id = parts[0]
          user_login = parts[1]
          image_url = parts[2]
          place_guess = parts[3]
          sci_name = parts[4].strip().lower()
          com_name = parts[5].strip().lower()

          observation_info = {
              "image_url": image_url,
              "place_guess": (
                  place_guess if place_guess else "Luogo sconosciuto"
              ),
              "user_login": user_login if user_login else "Anonimo",
              "obs_id": obs_id,
          }

          if sci_name:
            species_data_txt.setdefault(sci_name, []).append(observation_info)
          if com_name and com_name != "nan":
            species_data_txt.setdefault(com_name, []).append(observation_info)

  return species_data, species_data_txt


species_data, species_data_txt = load_game_data()

# --- 3. PROBABILITÀ E PESCAGGIO ---
slots_probs = [
    {"EXCO": 25, "COM": 75},
    {"EXCO": 14, "COM": 75, "BLUNC": 11},
    {"COM": 15, "BLUNC": 35, "UNC": 35, "RARE": 10, "EXRA": 5},
    {
        "COM": 9,
        "BLUNC": 25,
        "UNC": 30,
        "RARE": 25,
        "EXRA": 10,
        "ULTRA": 1,
    },
    {"BLUNC": 5, "UNC": 15, "RARE": 27, "EXRA": 45, "ULTRA": 8},
]


def draw_card(slot_index):
  prob_dict = slots_probs[slot_index]
  rarities = list(prob_dict.keys())
  weights = list(prob_dict.values())
  chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]

  matching_species = [
      s
      for s in species_data
      if s.get("Rarità", "").strip().upper() == chosen_rarity
  ]
  if not matching_species:
    matching_species = species_data

  chosen_species = random.choice(matching_species)
  common_name = chosen_species.get("Nome Comune", "Sconosciuto")
  latin_name = chosen_species.get("Nome Latino", "Sconosciuto")
  rarity = chosen_species.get("Rarità", chosen_rarity)

  image_url = "https://via.placeholder.com/300?text=No+Image"
  place_guess = "Luogo sconosciuto"
  user_login = "Anonimo"
  obs_id = ""

  matched_obs = None
  l_lower = latin_name.lower()
  matching_obs_list = []

  for sci_key, obs_list in species_data_txt.items():
    if l_lower in sci_key or sci_key in l_lower:
      matching_obs_list.extend(obs_list)

  if not matching_obs_list and common_name and common_name != "nan":
    c_lower = common_name.lower()
    for com_key, obs_list in species_data_txt.items():
      if c_lower in com_key or com_key in c_lower:
        matching_obs_list.extend(obs_list)

  if matching_obs_list:
    matched_obs = random.choice(matching_obs_list)

  if matched_obs:
    image_url = matched_obs["image_url"]
    place_guess = matched_obs["place_guess"]
    user_login = matched_obs["user_login"]
    obs_id = matched_obs["obs_id"]

  # Verifichiamo se è nuova consultando il DB su Google Sheets
  df_user = load_all_cards_from_gsheets()
  user_cards = df_user[df_user["player_name"] == current_user]
  is_new_species = common_name not in user_cards["common_name"].values

  card_data = {
      "common_name": common_name,
      "latin_name": latin_name,
      "rarity": rarity,
      "image_url": image_url,
      "place_guess": place_guess,
      "user_login": user_login,
      "obs_id": obs_id,
      "is_new": is_new_species,
  }

  save_card_to_gsheets(card_data, current_user)
  return card_data


# --- 4. COLORI DI RARITÀ ---
rarity_theme = {
    "EXCO": {"bg": "#34495e", "border": "#2c3e50", "text": "#ecf0f1"},
    "COM": {"bg": "#27ae60", "border": "#1e8449", "text": "#ecf0f1"},
    "BLUNC": {"bg": "#2980b9", "border": "#1f618d", "text": "#ecf0f1"},
    "UNC": {"bg": "#8e44ad", "border": "#6c3483", "text": "#ecf0f1"},
    "RARE": {"bg": "#f39c12", "border": "#d68910", "text": "#ffffff"},
    "EXRA": {"bg": "#d35400", "border": "#ba4a00", "text": "#ffffff"},
    "ULTRA": {"bg": "#c0392b", "border": "#962d22", "text": "#ffffff"},
}

# --- 5. GESTIONE STATO ---
if "page" not in st.session_state:
  st.session_state.page = "menu"
if "current_pack_cards" not in st.session_state:
  st.session_state.current_pack_cards = []
if "current_card_index" not in st.session_state:
  st.session_state.current_card_index = 0
if "selected_species" not in st.session_state:
  st.session_state.selected_species = None

# --- 6. INTERFACCIA APPLICAZIONE ---

# A. MENU PRINCIPALE
if st.session_state.page == "menu":
  st.markdown(
      f"<div style='text-align: center; padding: 25px; background: #427a4d;"
      f" border-radius: 12px; border: 1px solid #dee2e6; font-family: Arial;'>"
      f"<h2>🐾 iNaturalist TCG</h2><p style='color: #ffd700; font-weight: bold;"
      f" margin: 5px 0;'>Giocatore: {current_user.capitalize()}</p><p"
      " style='color: #ffffff; margin-bottom: 0;'>Apri le bustine e colleziona"
      " tutte le specie nell'album!</p></div>",
      unsafe_allow_html=True,
  )

  st.write("##")
  col1, col2 = st.columns([2, 1])
  with col1:
    pack_choice = st.selectbox(
        "Pacchetto:", ["Bustina Scimmie"], label_visibility="collapsed"
    )
  with col2:
    if st.button("Apri Bustina 🎁", use_container_width=True, type="primary"):
      with st.spinner("Apertura bustina in corso..."):
        time.sleep(1.0)
        st.session_state.current_pack_cards = [draw_card(i) for i in range(5)]
        st.session_state.current_card_index = 0
        st.session_state.page = "pack_opening"
        st.rerun()

  st.write("---")
  if st.button("📖 Apri Album & Pokedex", use_container_width=True):
    st.session_state.page = "album"
    st.rerun()

  st.write("---")
  if st.button("🔄 Cambia Profilo / Esci", use_container_width=True):
    st.session_state.player_name = None
    st.query_params.clear()
    st.rerun()

# B. APERTURA BUSTINA
elif st.session_state.page == "pack_opening":
  pack = st.session_state.current_pack_cards
  idx = st.session_state.current_card_index

  if idx < len(pack):
    c = pack[idx]
    r_key = c["rarity"].upper()
    theme = rarity_theme.get(
        r_key, {"bg": "#ffffff", "border": "#333", "text": "#333"}
    )
    is_rare_card = r_key in ["RARE", "EXRA", "ULTRA"]
    extra_style = (
        "animation: pulseGlow 1.5s infinite alternate; box-shadow: 0 0 20px"
        " #f1c40f, 0 10px 25px rgba(0,0,0,0.3) !important;"
        if is_rare_card
        else ""
    )
    new_badge = (
        "<div style='display: inline-block; background: #f1c40f; color:"
        " #2c3e50; font-weight: bold; padding: 4px 10px; border-radius: 20px;"
        " font-size: 11px; margin-bottom: 8px; box-shadow: 0 2px 5px"
        " rgba(0,0,0,0.2);'>✨ NUOVA SPECIE!</div>"
        if c.get("is_new", False)
        else ""
    )

    card_html = f"""<div style='text-align: center; font-family: Arial;'>
<h3 style='color: #2c3e50;'>🎴 Carta {idx + 1} di 5</h3>
{new_badge}
<div style='background-color: {theme['bg']}; border: 4px solid {theme['border']}; border-radius: 16px; width: 280px; padding: 14px; text-align: center; margin: 0 auto; color: {theme['text']}; {extra_style}'>
<div style='font-size: 11px; font-weight: bold; letter-spacing: 1.5px; margin-bottom: 6px; text-transform: uppercase;'>RARITÀ: {c['rarity']}</div>
<div style='background-color: #000; background-image: url("{c['image_url']}"); background-size: cover; background-position: center; border-radius: 10px; border: 2px solid rgba(255,255,255,0.2); width: 252px; height: 190px; margin: 0 auto;'></div>
<div style='font-weight: bold; font-size: 15px; margin-top: 10px;'>{c['common_name']}</div>
<div style='font-style: italic; font-size: 11px; opacity: 0.85; margin-top: 2px;'>{c['latin_name']}</div>
<div style='background: rgba(0, 0, 0, 0.25); border-radius: 8px; padding: 8px; margin-top: 8px; font-size: 11px; text-align: left; line-height: 1.4;'>
<div>📍 <b>Luogo:</b> {c['place_guess']}</div>
<div>📷 <b>Foto di:</b> {c['user_login']}</div>
</div>
</div>
</div>"""
    st.markdown(card_html, unsafe_allow_html=True)

    st.write("##")
    btn_label = (
        "✨ Mostra il riepilogo del pacchetto"
        if idx == len(pack) - 1
        else "Prossima Carta ➡️"
    )
    if st.button(btn_label, use_container_width=True, type="primary"):
      st.session_state.current_card_index += 1
      st.rerun()

  else:
    html_summary = f"""<div style='text-align: center;'>
<h2>🎉 Riepilogo Pacchetto: Ecco le 5 carte trovate!</h2>
<p style='color: #666; margin-bottom: 20px;'>Tutte le carte sono state salvate in modo permanente sul tuo Google Sheet!</p>
<div style='display: flex; flex-wrap: wrap; gap: 12px; justify-content: center;'>"""

    for i, c in enumerate(pack):
      r_key = c["rarity"].upper()
      theme = rarity_theme.get(
          r_key, {"bg": "#ffffff", "border": "#333", "text": "#333"}
      )
      summary_badge = (
          """<div style='background: #f1c40f; color: #000; font-size: 9px; font-weight: bold; border-radius: 4px; margin-bottom: 4px; padding: 2px 4px;'>✨ NUOVA!</div>"""
          if c.get("is_new", False)
          else ""
      )

      html_summary += f"""<div style='background-color: {theme['bg']}; border: 3px solid {theme['border']}; border-radius: 12px; width: 155px; padding: 8px; text-align: center; color: {theme['text']};'>
{summary_badge}
<div style='font-size: 10px; font-weight: bold;'>#{i+1} - {c['rarity']}</div>
<div style='background-color: #000; background-image: url("{c['image_url']}"); background-size: cover; background-position: center; width: 100%; height: 100px; border-radius: 6px;'></div>
<div style='font-weight: bold; font-size: 11px; margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{c['common_name']}</div>
</div>"""

    html_summary += "</div></div>"
    st.markdown(html_summary, unsafe_allow_html=True)
    st.write("---")

    col_a, col_b = st.columns(2)
    with col_a:
      if st.button("Torna al Menu 🏠", use_container_width=True):
        st.session_state.page = "menu"
        st.rerun()
    with col_b:
      if st.button("📖 Apri Album", use_container_width=True, type="primary"):
        st.session_state.page = "album"
        st.rerun()

# C. SOTTO-ALBUM SPECIFICO DELLA SPECIE
elif st.session_state.page == "species_detail":
  safe_name = st.session_state.selected_species
  df_all = load_all_cards_from_gsheets()

  # Ricaviamo il nome comune e i dati della specie dal DF
  user_cards = df_all[df_all["player_name"] == current_user]
  matched_rows = user_cards[
      user_cards["common_name"].str.replace("/", "_").str.replace(" ", "_").str.lower()
      == safe_name
  ]

  cover_obs_id = st.query_params.get("set_cover", None)
  if cover_obs_id is not None:
    if not matched_rows.empty:
      c_name = matched_rows.iloc[0]["common_name"]
      update_cover_in_gsheets(current_user, c_name, cover_obs_id)
      del st.query_params["set_cover"]
      st.success("⭐ Copertina aggiornata con successo!")
      time.sleep(0.5)
      st.rerun()

  if not matched_rows.empty:
    c_name = matched_rows.iloc[0]["common_name"]
    l_name = matched_rows.iloc[0]["latin_name"]
    rarity = matched_rows.iloc[0]["rarity"]
  else:
    c_name, l_name, rarity = safe_name, "", ""

  st.markdown(
      f"""<div style='font-family: Arial; text-align: center;'>
<h2>📚 Album Dedicato: {c_name}</h2>
<p style='font-style: italic; color: #555;'>{l_name} | Rarità: <b>{rarity}</b> | Esemplari collezionati: <b>{len(matched_rows)}</b></p>
</div>""",
      unsafe_allow_html=True,
  )

  html_grid = "<div style='font-family: Arial; display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; margin-top: 10px;'>"
  for idx, (_, c) in enumerate(matched_rows.iterrows()):
    r_key = str(c["rarity"]).upper()
    theme = rarity_theme.get(
        r_key, {"bg": "#ffffff", "border": "#333", "text": "#333"}
    )
    is_cover = bool(c["is_cover"]) or (
        idx == 0 and not matched_rows["is_cover"].any()
    )

    badge_text = f"⭐ Copertina (Copia #{idx+1})" if is_cover else f"Copia #{idx+1}"
    badge_bg = "#f1c40f" if is_cover else "#e74c3c"
    badge_color = "#000" if is_cover else "#fff"

    html_grid += f"""<div style='background-color: {theme['bg']}; border: 3px solid {theme['border']}; border-radius: 12px; width: 210px; padding: 10px; text-align: center; color: {theme['text']}; display: flex; flex-direction: column; justify-content: space-between;'>
<div>
    <div style='background: {badge_bg}; color: {badge_color}; border-radius: 6px; padding: 3px 6px; font-size: 9px; font-weight: bold; margin-bottom: 6px; display: inline-block;'>{badge_text}</div>
    <img src='{c['image_url']}' style='width: 100%; height: 120px; object-fit: cover; border-radius: 6px;' onerror="this.src='https://via.placeholder.com/150?text=No+Image'">
    <div style='background: rgba(0, 0, 0, 0.25); border-radius: 6px; padding: 6px; margin-top: 8px; font-size: 10px; text-align: left;'>
    <div>📍 <b>Luogo:</b> {c['place_guess']}</div>
    <div>📷 <b>Foto:</b> {c['user_login']}</div>
    </div>
</div>
<div>
    <div style='margin-top: 8px;'>
        <a href='?user={current_user}&species={safe_name}&set_cover={c['obs_id']}' target='_self' style='display: block; background: #f39c12; color: white; text-decoration: none; padding: 5px; border-radius: 6px; font-size: 10px; font-weight: bold;'>⭐ Imposta Copertina</a>
    </div>
</div>
</div>"""
  html_grid += "</div>"
  st.markdown(html_grid, unsafe_allow_html=True)

  st.write("##")
  col_b1, col_b2 = st.columns(2)
  with col_b1:
    if st.button("└── Torna all'Album", use_container_width=True):
      st.session_state.page = "album"
      st.rerun()
  with col_b2:
    if st.button("Torna al Menu 🏠", use_container_width=True):
      st.session_state.page = "menu"
      st.rerun()

# D. VISUALIZZAZIONE ALBUM GENERALE
elif st.session_state.page == "album":
  if st.button("Torna al Menu 🏠", use_container_width=True):
    st.session_state.page = "menu"
    st.rerun()

  df_all = load_all_cards_from_gsheets()
  user_cards = df_all[df_all["player_name"] == current_user]

  unlocked_species = {}
  for c_name, group in user_cards.groupby("common_name"):
    safe_name = c_name.replace("/", "_").replace(" ", "_").lower()
    cover_row = group[group["is_cover"] == True]
    sample = cover_row.iloc[0] if not cover_row.empty else group.iloc[0]
    unlocked_species[safe_name] = {"count": len(group), "sample": sample}

  total_species = len(species_data)
  found_count = len(unlocked_species)
  percentage = (
      int((found_count / total_species) * 100) if total_species > 0 else 0
  )

  st.markdown(
      f"""<div style='font-family: Arial; text-align: center;'>
<h2>📖 Album di {current_user.capitalize()}</h2>
<p style='color: #666;'>Specie sbloccate: <b>{found_count}</b> su <b>{total_species}</b> totali ({percentage}% completato)</p>
</div>""",
      unsafe_allow_html=True,
  )

  # --- FILTRI ---
  st.write("---")
  all_rarities = sorted(
      list(set(sp.get("Rarità", "COM").upper() for sp in species_data))
  )
  all_genera = sorted(
      list(
          set(
              sp.get("Nome Latino", "").strip().split()[0]
              for sp in species_data
              if sp.get("Nome Latino")
          )
      )
  )

  col_f1, col_f2 = st.columns(2)
  with col_f1:
    filter_rarity = st.selectbox("Filtra per Rarità:", ["Tutte"] + all_rarities)
  with col_f2:
    filter_genus = st.selectbox("Filtra per Genere:", ["Tutti"] + all_genera)

  filtered_species = species_data
  if filter_rarity != "Tutte":
    filtered_species = [
        sp
        for sp in filtered_species
        if sp.get("Rarità", "").upper() == filter_rarity
    ]
  if filter_genus != "Tutti":
    filtered_species = [
        sp
        for sp in filtered_species
        if sp.get("Nome Latino", "").strip().startswith(filter_genus)
    ]

  # GRIGLIA
  html_album_grid = "<div style='font-family: Arial; display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-top: 10px;'>"

  for sp in filtered_species:
    c_name = sp.get("Nome Comune", "Sconosciuto")
    l_name = sp.get("Nome Latino", "Sconosciuto")
    safe_name = c_name.replace("/", "_").replace(" ", "_").lower()

    if safe_name in unlocked_species:
      data = unlocked_species[safe_name]
      cnt = data["count"]
      sample_card = data["sample"]
      r_key = str(sample_card["rarity"]).upper()
      theme = rarity_theme.get(
          r_key, {"bg": "#27ae60", "border": "#1e8449", "text": "#ecf0f1"}
      )

      html_album_grid += f"""<div style='background-color: {theme['bg']}; border: 3px solid {theme['border']}; border-radius: 12px; width: 155px; padding: 8px; text-align: center; color: {theme['text']}; display: flex; flex-direction: column; justify-content: space-between;'>
<div>
    <div style='font-size: 10px; font-weight: bold;'>{r_key}</div>
    <div style='background-color: #000; background-image: url("{sample_card['image_url']}"); background-size: cover; background-position: center; width: 100%; height: 110px; border-radius: 6px;'></div>
    <div style='font-weight: bold; font-size: 11px; margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{c_name}</div>
    <div style='font-size: 9px; opacity: 0.85; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-style: italic;'>{l_name}</div>
</div>
<div style='margin-top: 8px;'>
    <a href='?user={current_user}&species={safe_name}' target='_self' style='display: block; background: rgba(0,0,0,0.3); color: white; text-decoration: none; padding: 5px; border-radius: 6px; font-size: 11px; font-weight: bold;'>x{cnt} copie 📖</a>
</div>
</div>"""
    else:
      html_album_grid += """<div style='background-color: #34495e; border: 3px dashed #7f8c8d; border-radius: 12px; width: 155px; padding: 8px; text-align: center; opacity: 0.5; color: #bdc3c7; display: flex; flex-direction: column; justify-content: space-between;'>
<div>
    <div style='font-size: 9px; font-weight: bold;'>MANCANTE</div>
    <div style='width: 100%; height: 110px; background: #2c3e50; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 24px;'>❓</div>
    <div style='font-weight: bold; font-size: 11px; margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>???</div>
    <div style='font-size: 9px; font-style: italic;'>Sconosciuto</div>
</div>
<div style='margin-top: 8px; background: rgba(0,0,0,0.2); padding: 5px; border-radius: 6px; font-size: 11px; color: #7f8c8d;'>🔒 x0 copie</div>
</div>"""

  html_album_grid += "</div>"
  st.markdown(html_album_grid, unsafe_allow_html=True)
