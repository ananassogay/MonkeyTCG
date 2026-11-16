import json
import os
import random
import time
import streamlit as st

# --- 1. CONFIGURAZIONE PAGINA E PERCORSI ---
st.set_page_config(
    page_title="iNaturalist TCG - Scimmie", page_icon="🐾", layout="centered"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(BASE_DIR, "scimmie.json")
TXT_FILE = os.path.join(BASE_DIR, "osservazioni.txt")

# --- 1.5 SCHERMATA LOGIN / NOME UTENTE ---
if "player_name" not in st.session_state:
  if "user" in st.query_params:
    st.session_state.player_name = st.query_params["user"]
  else:
    st.session_state.player_name = None

# Se l'utente non è ancora inserito, mostriamo solo la schermata di benvenuto
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
  st.stop()  # Ferma la pagina qui finché non viene digitato il nome

current_user = st.session_state.player_name

# Controlliamo se è stata selezionata una specie dall'album HTML
if "species" in st.query_params:
  st.session_state.selected_species = st.query_params["species"]
  st.session_state.page = "species_detail"
  del st.query_params["species"]

# Cartella dell'album unica per il giocatore
ALBUM_DIR = os.path.join(BASE_DIR, f"album_carte_{current_user}")
if not os.path.exists(ALBUM_DIR):
  os.makedirs(ALBUM_DIR)


# --- 2. CARICAMENTO DATI ---
@st.cache_data
def load_game_data():
  species_data = []
  if os.path.exists(JSON_FILE):
    with open(JSON_FILE, "r", encoding="utf-8") as f:
      species_data = json.load(f)

  species_data_txt = {}
  if os.path.exists(TXT_FILE):
    with open(TXT_FILE, "r", encoding="utf-8", errors="ignore") as f:
      f.readline()  # Skip header
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

# --- 3. REGOLE DELLE PROBABILITÀ E GESTIONE ALBUM ---
slots_probs = [
    {"EXCO": 25, "COM": 75},  # 1° carta
    {"EXCO": 14, "COM": 75, "BLUNC": 11},  # 2° carta
    {"COM": 15, "BLUNC": 35, "UNC": 35, "RARE": 10, "EXRA": 5},  # 3° carta
    {
        "COM": 9,
        "BLUNC": 25,
        "UNC": 30,
        "RARE": 25,
        "EXRA": 10,
        "ULTRA": 1,
    },  # 4° carta
    {"BLUNC": 5, "UNC": 15, "RARE": 27, "EXRA": 45, "ULTRA": 8},  # 5° carta
]


def load_species_copies(file_path):
  """Legge il file JSON della specie supportando sia il vecchio formato (lista) sia il nuovo (dizionario con cover_index)."""
  if not os.path.exists(file_path):
    return [], 0
  try:
    with open(file_path, "r", encoding="utf-8") as f:
      data = json.load(f)
      if isinstance(data, list):
        return data, 0
      elif isinstance(data, dict):
        return data.get("copies", []), data.get("cover_index", 0)
  except:
    pass
  return [], 0


def save_species_copies(file_path, copies, cover_index=0):
  """Salva i dati della specie mantenendo l'ordine dei doppioni e l'indice della copertina scelta."""
  data = {"cover_index": cover_index, "copies": copies}
  with open(file_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)


def save_card_to_album_folder(card):
  safe_name = (
      card["common_name"].replace("/", "_").replace(" ", "_").lower()
  )
  file_path = os.path.join(ALBUM_DIR, f"{safe_name}.json")

  copies, cover_index = load_species_copies(file_path)
  copies.append(card)
  save_species_copies(file_path, copies, cover_index)


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

  # --- LOGICA DI ABBINAMENTO FLESSIBILE PER NOME LATINO / COMUNE ---
  matched_obs = None
  
  # 1. Cerchiamo prima per corrispondenza parziale nel nome latino (es. cattura le sottospecie)
  l_lower = latin_name.lower()
  matching_obs_list = []
  
  for sci_key, obs_list in species_data_txt.items():
    # Se il nome della specie è contenuto nella chiave del txt (o viceversa)
    if l_lower in sci_key or sci_key in l_key:
      matching_obs_list.extend(obs_list)

  # 2. Se non troviamo nulla col latino, proviamo col nome comune
  if not matching_obs_list and common_name and common_name != "nan":
    c_lower = common_name.lower()
    for com_key, obs_list in species_data_txt.items():
      if c_lower in com_key or com_key in c_lower:
        matching_obs_list.extend(obs_list)

  # 3. Se abbiamo trovato delle osservazioni compatibili, ne peschiamo una a caso
  if matching_obs_list:
    matched_obs = random.choice(matching_obs_list)

  if matched_obs:
    image_url = matched_obs["image_url"]
    place_guess = matched_obs["place_guess"]
    user_login = matched_obs["user_login"]
    obs_id = matched_obs["obs_id"]

  safe_name = common_name.replace("/", "_").replace(" ", "_").lower()
  file_path = os.path.join(ALBUM_DIR, f"{safe_name}.json")

  is_new_species = not os.path.exists(file_path) or os.path.getsize(file_path) == 0

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

  save_card_to_album_folder(card_data)
  return card_data


def export_user_album_to_json():
  """Raccoglie tutte le carte salvate nella cartella dell'utente per l'export."""
  all_cards_data = {}
  if os.path.exists(ALBUM_DIR):
    for filename in os.listdir(ALBUM_DIR):
      if filename.endswith(".json"):
        file_path = os.path.join(ALBUM_DIR, filename)
        copies, cover_index = load_species_copies(file_path)
        if copies:
          all_cards_data[filename] = {"copies": copies, "cover_index": cover_index}
  return json.dumps(all_cards_data, ensure_ascii=False, indent=4)


def import_user_album_from_json(uploaded_file):
  """Legge un file JSON di backup e ripristina la collezione."""
  try:
    content = json.load(uploaded_file)
    if not os.path.exists(ALBUM_DIR):
      os.makedirs(ALBUM_DIR)

    for filename, data in content.items():
      file_path = os.path.join(ALBUM_DIR, filename)
      if isinstance(data, list):
        # Retrocompatibilità per vecchi backup in formato lista
        save_species_copies(file_path, data, 0)
      elif isinstance(data, dict):
        save_species_copies(file_path, data.get("copies", []), data.get("cover_index", 0))
    return True
  except Exception:
    return False


# --- 4. CONFIGURAZIONE COLORI DI RARITÀ ---
rarity_theme = {
    "EXCO": {"bg": "#34495e", "border": "#2c3e50", "text": "#ecf0f1"},
    "COM": {"bg": "#27ae60", "border": "#1e8449", "text": "#ecf0f1"},
    "BLUNC": {"bg": "#2980b9", "border": "#1f618d", "text": "#ecf0f1"},
    "UNC": {"bg": "#8e44ad", "border": "#6c3483", "text": "#ecf0f1"},
    "RARE": {"bg": "#f39c12", "border": "#d68910", "text": "#ffffff"},
    "EXRA": {"bg": "#d35400", "border": "#ba4a00", "text": "#ffffff"},
    "ULTRA": {"bg": "#c0392b", "border": "#962d22", "text": "#ffffff"},
}

# --- 5. GESTIONE STATO SESSIONE STREAMLIT ---
if "page" not in st.session_state:
  st.session_state.page = "menu"
if "current_pack_cards" not in st.session_state:
  st.session_state.current_pack_cards = []
if "current_card_index" not in st.session_state:
  st.session_state.current_card_index = 0
if "selected_species" not in st.session_state:
  st.session_state.selected_species = None

# --- 6. INTERFACCIA E FLUSSO APPLICAZIONE ---

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
      if pack_choice != "Bustina Scimmie":
        st.error("Questo pacchetto non è disponibile!")
      else:
        with st.spinner("Apertura bustina in corso..."):
          st.markdown(
              """<style>
@keyframes shake {
  0% { transform: translate(1px, 1px) rotate(0deg); }
  20% { transform: translate(-3px, 0px) rotate(-3deg); }
  40% { transform: translate(3px, 2px) rotate(3deg); }
  60% { transform: translate(-1px, -1px) rotate(0deg); }
  80% { transform: translate(3px, 1px) rotate(1deg); }
  100% { transform: translate(0px, 0px) rotate(0deg); }
}
.pack-container { text-align: center; padding: 20px; }
.booster-pack {
  display: inline-block;
  background: linear-gradient(135deg, #1b5e20, #4caf50);
  border: 4px solid #ffd700;
  border-radius: 15px;
  width: 220px;
  height: 320px;
  box-shadow: 0 10px 25px rgba(0,0,0,0.3);
  animation: shake 0.5s infinite;
  color: white;
  padding-top: 100px;
  font-family: Arial, sans-serif;
}
</style>
<div class='pack-container'>
    <div class='booster-pack'>
       <h1 style='color: #ffd700; text-shadow: 2px 2px 4px rgba(0,0,0,0.5);'>MONKEY<br>PACK</h1>
       <p style='font-size: 12px; margin-top: 50px;'>iNaturalist TCG</p>
    </div>
</div>""",
              unsafe_allow_html=True,
          )
          time.sleep(1.5)
          st.session_state.current_pack_cards = [
              draw_card(i) for i in range(5)
          ]
          st.session_state.current_card_index = 0
          st.session_state.page = "pack_opening"
          st.rerun()

  st.write("---")
  col_album = st.columns(1)[0]
  with col_album:
    if st.button("📖 Apri Album & Pokedex", use_container_width=True):
      st.session_state.page = "album"
      st.rerun()

  st.write("---")
  if st.button("🔄 Cambia Profilo / Esci", use_container_width=True):
    st.session_state.player_name = None
    st.query_params.clear()
    st.rerun()

# B. APERTURA BUSTINA & CARTE SINGOLE / RIEPILOGO
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
    extra_style = ""
    if is_rare_card:
      extra_style = "animation: pulseGlow 1.5s infinite alternate; box-shadow: 0 0 20px #f1c40f, 0 10px 25px rgba(0,0,0,0.3) !important;"

    new_badge = ""
    if c.get("is_new", False):
      new_badge = "<div style='display: inline-block; background: #f1c40f; color: #2c3e50; font-weight: bold; padding: 4px 10px; border-radius: 20px; font-size: 11px; margin-bottom: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);'>✨ NUOVA SPECIE!</div>"

    st.markdown("""
    <style>
    @keyframes pulseGlow {
        0% { border-color: #f1c40f; box-shadow: 0 0 10px rgba(241, 196, 15, 0.5), 0 10px 25px rgba(0,0,0,0.3); }
        100% { border-color: #e74c3c; box-shadow: 0 0 25px rgba(231, 76, 60, 0.8), 0 10px 25px rgba(0,0,0,0.3); }
    }
    </style>
    """, unsafe_allow_html=True)

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

    is_new_card = c.get("is_new", False)

    if is_new_card:
      sound_url = f"https://assets.mixkit.co/active_storage/sfx/866/866-preview.mp3?t={random.randint(1000, 9999)}"
      st.markdown(
          f"<audio src='{sound_url}' autoplay></audio>",
          unsafe_allow_html=True,
      )

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
<p style='color: #666; margin-bottom: 20px;'>Tutte le carte sono state aggiunte alla tua collezione e salvate nell'album.</p>
<div style='display: flex; flex-wrap: wrap; gap: 12px; justify-content: center;'>"""

    for i, c in enumerate(pack):
      r_key = c["rarity"].upper()
      theme = rarity_theme.get(
          r_key, {"bg": "#ffffff", "border": "#333", "text": "#333"}
      )

      summary_badge = ""
      if c.get("is_new", False):
        summary_badge = """<div style='background: #f1c40f; color: #000; font-size: 9px; font-weight: bold; border-radius: 4px; margin-bottom: 4px; padding: 2px 4px; text-transform: uppercase;'>
✨ NUOVA!
</div>"""

      html_summary += f"""<div style='background-color: {theme['bg']}; border: 3px solid {theme['border']}; border-radius: 12px; width: 155px; padding: 8px; text-align: center; box-shadow: 0 6px 15px rgba(0,0,0,0.2); color: {theme['text']};'>
{summary_badge}
<div style='font-size: 10px; font-weight: bold; margin-bottom: 4px;'>#{i+1} - {c['rarity']}</div>
<div style='background-color: #000; background-image: url("{c['image_url']}"); background-size: cover; background-position: center; width: 100%; height: 100px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.2);'></div>
<div style='font-weight: bold; font-size: 11px; margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{c['common_name']}</div>
<div style='font-size: 9px; opacity: 0.85; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{c['latin_name']}</div>
<div style='font-size: 8px; background: rgba(0,0,0,0.25); padding: 3px; border-radius: 4px; margin-top: 4px; text-align: left; line-height: 1.2;'>
<div>📍 {c['place_guess'][:18]}...</div>
<div>📷 {c['user_login']}</div>
</div>
</div>"""

    html_summary += "</div></div>"
    st.markdown(html_summary, unsafe_allow_html=True)
    st.write("---")

    col_a, col_b = st.columns(2)
    with col_a:
      if st.button(
          "Torna al Menu 🏠", use_container_width=True, key="menu_summary"
      ):
        st.session_state.page = "menu"
        st.rerun()
    with col_b:
      if st.button(
          "📖 Apri Album", use_container_width=True, type="primary"
      ):
        st.session_state.page = "album"
        st.rerun()

# C. SOTTO-ALBUM SPECIFICO DELLA SPECIE (DOPPIONI & COPERTINA)
elif st.session_state.page == "species_detail":
  safe_name = st.session_state.selected_species
  file_path = os.path.join(ALBUM_DIR, f"{safe_name}.json")

  copies, cover_index = load_species_copies(file_path)

  # GESTIONE CAMBIO COPERTINA
  cover_idx_to_set = st.query_params.get("set_cover", None)
  if cover_idx_to_set is not None:
    try:
      idx = int(cover_idx_to_set)
      if 0 <= idx < len(copies):
        save_species_copies(file_path, copies, cover_index=idx)
        del st.query_params["set_cover"]
        st.success("⭐ Copertina aggiornata con successo!")
        time.sleep(0.5)
        st.rerun()
    except Exception:
      pass

  if copies:
    c_name = copies[0]["common_name"]
    l_name = copies[0]["latin_name"]
    rarity = copies[0]["rarity"]
  else:
    c_name = safe_name
    l_name = ""
    rarity = ""

  st.markdown(
      f"""<div style='font-family: Arial; text-align: center;'>
<h2>📚 Album Dedicato: {c_name}</h2>
<p style='font-style: italic; color: #555;'>{l_name} | Rarità: <b>{rarity}</b> | Esemplari collezionati: <b>{len(copies)}</b></p>
<p style='color: #27ae60; font-size: 12px; margin-bottom: 20px;'>✨ La carta contrassegnata in giallo è attualmente in mostra come copertina nell'Album Generale.</p>
</div>""",
      unsafe_allow_html=True,
  )

  html_grid = "<div style='font-family: Arial; display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; margin-top: 10px;'>"
  for idx, c in enumerate(copies):
    r_key = c["rarity"].upper()
    theme = rarity_theme.get(
        r_key, {"bg": "#ffffff", "border": "#333", "text": "#333"}
    )
    inat_url = (
        f"https://www.inaturalist.org/observations/{c['obs_id']}"
        if c.get("obs_id")
        else "https://www.inaturalist.org"
    )
    wiki_url = f"https://it.wikipedia.org/wiki/Special:Search?search={c['latin_name']}"

    is_current_cover = idx == cover_index
    badge_text = (
        f"⭐ Copertina (Copia #{idx+1})"
        if is_current_cover
        else f"Copia #{idx+1}"
    )
    badge_bg = "#f1c40f" if is_current_cover else "#e74c3c"
    badge_color = "#000" if is_current_cover else "#fff"

    html_grid += f"""<div style='background-color: {theme['bg']}; border: 3px solid {theme['border']}; border-radius: 12px; width: 210px; padding: 10px; text-align: center; box-shadow: 0 6px 15px rgba(0,0,0,0.25); color: {theme['text']}; display: flex; flex-direction: column; justify-content: space-between;'>
<div>
    <div style='background: {badge_bg}; color: {badge_color}; border-radius: 6px; padding: 3px 6px; font-size: 9px; font-weight: bold; margin-bottom: 6px; display: inline-block;'>{badge_text}</div>
    <img src='{c['image_url']}' style='width: 100%; height: 120px; object-fit: cover; border-radius: 6px; border: 1px solid rgba(255,255,255,0.2);' onerror="this.src='https://via.placeholder.com/150?text=No+Image'">
    <div style='background: rgba(0, 0, 0, 0.25); border-radius: 6px; padding: 6px; margin-top: 8px; font-size: 10px; text-align: left; line-height: 1.3;'>
    <div>📍 <b>Luogo:</b> {c['place_guess']}</div>
    <div>📷 <b>Foto:</b> {c['user_login']}</div>
    </div>
</div>
<div>
    <div style='margin-top: 8px;'>
        <a href='?user={current_user}&species={safe_name}&set_cover={idx}' target='_self' style='display: block; background: #f39c12; color: white; text-decoration: none; padding: 5px; border-radius: 6px; font-size: 10px; font-weight: bold; border: 1px solid rgba(255,255,255,0.3);'>⭐ Imposta Copertina</a>
    </div>
    <div style='margin-top: 6px; display: flex; justify-content: space-around; font-size: 11px; font-weight: bold;'>
    <a href='{inat_url}' target='_blank' style='color: {theme['text']}; text-decoration: underline;'>vedi oss.</a>
    <a href='{wiki_url}' target='_blank' style='color: {theme['text']}; text-decoration: underline;'>info wiki</a>
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
    if st.button(
        "Torna al Menu 🏠", use_container_width=True, key="menu_species_detail"
    ):
      st.session_state.page = "menu"
      st.rerun()

# D. VISUALIZZAZIONE ALBUM GENERALE
elif st.session_state.page == "album":
  if st.button(
      "Torna al Menu 🏠", use_container_width=True, key="menu_album_top"
  ):
    st.session_state.page = "menu"
    st.rerun()

  unlocked_species = {}
  if os.path.exists(ALBUM_DIR):
    for filename in os.listdir(ALBUM_DIR):
      if filename.endswith(".json"):
        file_path = os.path.join(ALBUM_DIR, filename)
        try:
          copies, cover_index = load_species_copies(file_path)
          if copies:
            safe_name = filename.replace(".json", "")
            safe_cover_idx = (
                cover_index if 0 <= cover_index < len(copies) else 0
            )
            unlocked_species[safe_name] = {
                "copies": copies,
                "cover_index": safe_cover_idx,
                "sample_card": copies[safe_cover_idx],
            }
        except:
          pass

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

  # --- SEZIONE FILTRI PER RARITÀ E GENERE ---
  st.write("---")
  st.markdown("### 🔍 Filtri Album")

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

  st.markdown(
      f"<p style='font-size: 13px; color: #555; text-align: center;'>Visualizzando"
      f" <b>{len(filtered_species)}</b> specie in base ai filtri"
      " selezionati.</p>",
      unsafe_allow_html=True,
  )
  st.write("---")

  # --- GRIGLIA FLUIDA STILE RIEPILOGO PACCHETTO ---
  html_album_grid = "<div style='font-family: Arial; display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; margin-top: 10px;'>"

  for sp in filtered_species:
    c_name = sp.get("Nome Comune", "Sconosciuto")
    l_name = sp.get("Nome Latino", "Sconosciuto")
    safe_name = c_name.replace("/", "_").replace(" ", "_").lower()

    if safe_name in unlocked_species:
      item_data = unlocked_species[safe_name]
      copies_list = item_data["copies"]
      cnt = len(copies_list)
      sample_card = item_data["sample_card"]
      r_key = sample_card["rarity"].upper()
      theme = rarity_theme.get(
          r_key, {"bg": "#27ae60", "border": "#1e8449", "text": "#ecf0f1"}
      )

      html_album_grid += f"""<div style='background-color: {theme['bg']}; border: 3px solid {theme['border']}; border-radius: 12px; width: 155px; padding: 8px; text-align: center; box-shadow: 0 6px 15px rgba(0,0,0,0.2); color: {theme['text']}; display: flex; flex-direction: column; justify-content: space-between;'>
<div>
    <div style='font-size: 10px; font-weight: bold; margin-bottom: 4px; text-transform: uppercase;'>{r_key}</div>
    <div style='background-color: #000; background-image: url("{sample_card['image_url']}"); background-size: cover; background-position: center; width: 100%; height: 110px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.2);'></div>
    <div style='font-weight: bold; font-size: 11px; margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{c_name}</div>
    <div style='font-size: 9px; opacity: 0.85; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-style: italic;'>{l_name}</div>
</div>
<div style='margin-top: 8px;'>
    <a href='?user={current_user}&species={safe_name}' target='_self' style='display: block; background: rgba(0,0,0,0.3); color: white; text-decoration: none; padding: 5px; border-radius: 6px; font-size: 11px; font-weight: bold; border: 1px solid rgba(255,255,255,0.2);'>x{cnt} copie 📖</a>
</div>
</div>"""
    else:
      html_album_grid += """<div style='background-color: #34495e; border: 3px dashed #7f8c8d; border-radius: 12px; width: 155px; padding: 8px; text-align: center; opacity: 0.5; color: #bdc3c7; display: flex; flex-direction: column; justify-content: space-between;'>
<div>
    <div style='font-size: 9px; font-weight: bold; margin-bottom: 4px;'>MANCANTE</div>
    <div style='width: 100%; height: 110px; background: #2c3e50; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 24px;'>❓</div>
    <div style='font-weight: bold; font-size: 11px; margin-top: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>???</div>
    <div style='font-size: 9px; font-style: italic; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>Sconosciuto</div>
</div>
<div style='margin-top: 8px; background: rgba(0,0,0,0.2); padding: 5px; border-radius: 6px; font-size: 11px; font-weight: bold; color: #7f8c8d;'>
    🔒 x0 copie
</div>
</div>"""

  html_album_grid += "</div>"
  st.markdown(html_album_grid, unsafe_allow_html=True)
  st.write("")

  # --- PANNELLO BACKUP & RIPRISTINO ALBUM ---
  st.write("---")
  with st.expander("💾 Backup e Ripristino Collezione (Cambio Dispositivo)"):
    st.markdown(
        "<p style='font-size: 13px; color: #555;'>Scarica un file di backup"
        " per trasferire le tue carte su un altro telefono o ripristina una"
        " collezione precedentemente salvata.</p>",
        unsafe_allow_html=True,
    )

    col_exp, col_imp = st.columns(2)

    with col_exp:
      json_data = export_user_album_to_json()
      st.download_button(
          label="⬇️ Scarica Backup Album",
          data=json_data,
          file_name=f"backup_album_{current_user}.json",
          mime="application/json",
          use_container_width=True,
      )

    with col_imp:
      uploaded_backup = st.file_uploader(
          "Carica backup (.json)", type=["json"], label_visibility="collapsed"
      )
      if uploaded_backup is not None:
        if st.button("🔄 Ripristina Album", use_container_width=True):
          if import_user_album_from_json(uploaded_backup):
            st.success("✅ Album ripristinato con successo!")
            time.sleep(1)
            st.rerun()
          else:
            st.error("❌ Errore durante il ripristino del file.")

  st.write("---")
  if st.button(
      "Torna al Menu 🏠", use_container_width=True, key="menu_album_bottom"
  ):
    st.session_state.page = "menu"
    st.rerun()
