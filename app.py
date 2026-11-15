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
ALBUM_DIR = os.path.join(BASE_DIR, "album_carte")

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
              "place_guess": place_guess if place_guess else "Luogo sconosciuto",
              "user_login": user_login if user_login else "Anonimo",
              "obs_id": obs_id,
          }

          if sci_name:
            species_data_txt.setdefault(sci_name, []).append(observation_info)
          if com_name and com_name != "nan":
            species_data_txt.setdefault(com_name, []).append(observation_info)

  return species_data, species_data_txt


species_data, species_data_txt = load_game_data()

# --- 3. REGOLE DELLE PROBABILITÀ PER LE 5 CARTE ---
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
    {"BLUNC": 10, "UNC": 25, "RARE": 15, "EXRA": 45, "ULTRA": 5},  # 5° carta
]


def save_card_to_album_folder(card):
  safe_name = (
      card["common_name"].replace("/", "_").replace(" ", "_").lower()
  )
  file_path = os.path.join(ALBUM_DIR, f"{safe_name}.json")

  existing_copies = []
  if os.path.exists(file_path):
    try:
      with open(file_path, "r", encoding="utf-8") as f:
        existing_copies = json.load(f)
    except:
      existing_copies = []

  existing_copies.append(card)

  with open(file_path, "w", encoding="utf-8") as f:
    json.dump(existing_copies, f, ensure_ascii=False, indent=4)


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
  if latin_name.lower() in species_data_txt:
    matched_obs = random.choice(species_data_txt[latin_name.lower()])
  elif common_name.lower() in species_data_txt:
    matched_obs = random.choice(species_data_txt[common_name.lower()])

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
      "<div style='text-align: center; padding: 30px; background: #427a4d;"
      " border-radius: 12px; border: 1px solid #dee2e6; font-family: Arial;'>"
      "<h2>🐾 iNaturalist TCG - Menu Principale</h2><p style='color: #ffffff;"
      " margin-bottom: 20px;'>Apri le bustine e colleziona tutte le specie"
      " nell'album!</p></div>",
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
          st.session_state.current_pack_cards = [draw_card(i) for i in range(5)]
          st.session_state.current_card_index = 0
          st.session_state.page = "pack_opening"
          st.rerun()

  st.write("---")
  col_album = st.columns(1)[0]
  with col_album:
    if st.button("📖 Apri Album & Pokedex", use_container_width=True):
      st.session_state.page = "album"
      st.rerun()

# B. APERTURA BUSTINA & CARTE SINGOLE / RIEPILOGO
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

    # === BLOCCO 1: Logica per individuare se la carta è rara e preparare l'effetto ===
    is_rare_card = r_key in ["RARE", "EXRA", "ULRA"]
    extra_style = ""
    if is_rare_card:
        extra_style = "animation: pulseGlow 1.5s infinite alternate; box-shadow: 0 0 20px #f1c40f, 0 10px 25px rgba(0,0,0,0.3) !important;"

    new_badge = ""
    if c.get("is_new", False):
      new_badge = "<div style='display: inline-block; background: #f1c40f; color: #2c3e50; font-weight: bold; padding: 4px 10px; border-radius: 20px; font-size: 11px; margin-bottom: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);'>✨ NUOVA SPECIE!</div>"

    # === BLOCCO 2: Iniezione dello stile CSS e la carta aggiornata con {extra_style} ===
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
    # Controlliamo se la carta è una nuova scoperta (is_new)
    is_new_card = c.get("is_new", False)

    # ... (tutto il resto del codice della carta) ...
    st.markdown(card_html, unsafe_allow_html=True)

    # Suona l'audio SOLO se la carta è una nuova scoperta!
    if is_new_card:
      st.markdown(
          "<audio"
          " src='https://assets.mixkit.co/active_storage/sfx/866/866-preview.mp3'"
          " autoplay></audio>",
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
      if st.button("Torna al Menu 🏠", use_container_width=True):
        st.session_state.page = "menu"
        st.rerun()
    with col_b:
      if st.button(
          "📖 Apri Album", use_container_width=True, type="primary"
      ):
        st.session_state.page = "album"
        st.rerun()

# C. SOTTO-ALBUM SPECIFICO DELLA SPECIE (DOPPIONI)
elif st.session_state.page == "species_detail":
  safe_name = st.session_state.selected_species
  file_path = os.path.join(ALBUM_DIR, f"{safe_name}.json")

  copies = []
  if os.path.exists(file_path):
    try:
      with open(file_path, "r", encoding="utf-8") as f:
        copies = json.load(f)
    except:
      copies = []

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
<p style='color: #27ae60; font-size: 12px; margin-bottom: 20px;'>✨ Stai visualizzando esclusivamente le carte appartenenti a questa specie.</p>
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

    html_grid += f"""<div style='background-color: {theme['bg']}; border: 3px solid {theme['border']}; border-radius: 12px; width: 210px; padding: 10px; text-align: center; box-shadow: 0 6px 15px rgba(0,0,0,0.25); color: {theme['text']};'>
<div style='background: #e74c3c; color: white; border-radius: 8px; padding: 2px 6px; font-size: 10px; font-weight: bold; margin-bottom: 6px; display: inline-block;'>Copia #{idx+1}</div>
<img src='{c['image_url']}' style='width: 100%; height: 120px; object-fit: cover; border-radius: 6px; border: 1px solid rgba(255,255,255,0.2);' onerror="this.src='https://via.placeholder.com/150?text=No+Image'">
<div style='background: rgba(0, 0, 0, 0.25); border-radius: 6px; padding: 6px; margin-top: 8px; font-size: 10px; text-align: left; line-height: 1.3;'>
<div>📍 <b>Luogo:</b> {c['place_guess']}</div>
<div>📷 <b>Foto:</b> {c['user_login']}</div>
</div>
<div style='margin-top: 8px; display: flex; justify-content: space-around; font-size: 11px; font-weight: bold;'>
<a href='{inat_url}' target='_blank' style='color: {theme['text']}; text-decoration: underline;'>vedi oss.</a>
<a href='{wiki_url}' target='_blank' style='color: {theme['text']}; text-decoration: underline;'>info wiki</a>
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

  unlocked_species = {}
  if os.path.exists(ALBUM_DIR):
    for filename in os.listdir(ALBUM_DIR):
      if filename.endswith(".json"):
        file_path = os.path.join(ALBUM_DIR, filename)
        try:
          with open(file_path, "r", encoding="utf-8") as f:
            copies = json.load(f)
            if copies:
              safe_name = filename.replace(".json", "")
              unlocked_species[safe_name] = copies
        except:
          pass

  total_species = len(species_data)
  found_count = len(unlocked_species)
  percentage = (
      int((found_count / total_species) * 100) if total_species > 0 else 0
  )

  st.markdown(
      f"""<div style='font-family: Arial; text-align: center;'>
<h2>📖 Album & Pokedex iNaturalist</h2>
<p style='color: #666;'>Specie sbloccate: <b>{found_count}</b> su <b>{total_species}</b> totali ({percentage}% completato)<br>
<i>💡 Clicca sul pulsante delle copie di qualsiasi carta per aprire il sotto-album dedicato!</i></p>
</div>""",
      unsafe_allow_html=True,
  )
  st.write("---")

  grid_cols = st.columns(4)
  for idx, sp in enumerate(species_data):
    c_name = sp.get("Nome Comune", "Sconosciuto")
    l_name = sp.get("Nome Latino", "Sconosciuto")
    safe_name = c_name.replace("/", "_").replace(" ", "_").lower()

    col_target = grid_cols[idx % 4]
    with col_target:
      if safe_name in unlocked_species:
        copies_list = unlocked_species[safe_name]
        cnt = len(copies_list)
        sample_card = copies_list[0]
        r_key = sample_card["rarity"].upper()
        theme = rarity_theme.get(
            r_key, {"bg": "#27ae60", "border": "#1e8449", "text": "#ecf0f1"}
        )

        st.markdown(
            f"""<div style='background-color: {theme['bg']}; border: 3px solid {theme['border']}; border-radius: 10px 10px 0 0; padding: 6px; text-align: center; color: {theme['text']}; font-family: Arial;'>
<img src='{sample_card['image_url']}' style='width: 100%; height: 75px; object-fit: cover; border-radius: 5px; border: 1px solid rgba(255,255,255,0.2);' onerror="this.src='https://via.placeholder.com/150?text=No+Image'">
<div style='font-weight: bold; font-size: 10px; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{c_name}</div>
<div style='font-size: 8px; opacity: 0.85; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{l_name}</div>
</div>""",
            unsafe_allow_html=True,
        )

        if st.button(
            f"x{cnt} copie", key=f"btn_{safe_name}", use_container_width=True
        ):
          st.session_state.selected_species = safe_name
          st.session_state.page = "species_detail"
          st.rerun()
      else:
        st.markdown(
            """<div style='background-color: #34495e; border: 3px dashed #7f8c8d; border-radius: 10px; padding: 6px; text-align: center; opacity: 0.5; color: #bdc3c7; font-family: Arial;'>
<div style='font-size: 8px; font-weight: bold; margin-bottom: 3px;'>MANCANTE</div>
<div style='width: 100%; height: 75px; background: #2c3e50; border-radius: 5px; display: flex; align-items: center; justify-content: center; font-size: 20px;'>❓</div>
<div style='font-weight: bold; font-size: 10px; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>???</div>
<div style='font-size: 8px; font-style: italic; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>Sconosciuto</div>
</div>""",
            unsafe_allow_html=True,
        )
      st.write("")

  st.write("---")
  if st.button("Torna al Menu 🏠", use_container_width=True):
    st.session_state.page = "menu"
    st.rerun()
