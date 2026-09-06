/* ==========================================================
   SOLO LEVELING HUNTER SYSTEM - CLIENT APP LOGIC
   ========================================================== */

// --- Audio Synthesizer (Web Audio API) ---
class SoundFX {
  constructor() {
    this.ctx = null;
    this.muted = localStorage.getItem('sound_muted') === 'true';
  }

  init() {
    if (!this.ctx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      this.ctx = new AudioContext();
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  playTone(freq, duration, type = 'sine', gainVal = 0.15, delay = 0) {
    if (this.muted) return;
    this.init();
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    const startTime = this.ctx.currentTime + delay;

    osc.type = type;
    osc.frequency.setValueAtTime(freq, startTime);
    
    gain.gain.setValueAtTime(gainVal, startTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);

    osc.connect(gain);
    gain.connect(this.ctx.destination);

    osc.start(startTime);
    osc.stop(startTime + duration);
  }

  playSystemNotification() {
    // Solo Leveling [SYSTEM] 3-note high-tech arpeggio
    this.playTone(587.33, 0.12, 'sine', 0.15, 0);       // D5
    this.playTone(880.00, 0.12, 'sine', 0.18, 0.08);    // A5
    this.playTone(1174.66, 0.35, 'triangle', 0.22, 0.16); // D6
  }

  playLevelUp() {
    // Epic Level-Up Fanfare
    const notes = [440, 554.37, 659.25, 880, 1108.73, 1318.51];
    notes.forEach((freq, idx) => {
      this.playTone(freq, 0.35, 'triangle', 0.2, idx * 0.09);
    });
    setTimeout(() => {
      this.playTone(880, 0.6, 'sawtooth', 0.1, 0.55);
      this.playTone(1760, 0.8, 'sine', 0.25, 0.55);
    }, 100);
  }

  playPotion() {
    // Potion drink water drop effect
    this.playTone(400, 0.08, 'sine', 0.12, 0);
    this.playTone(720, 0.15, 'sine', 0.2, 0.06);
    this.playTone(980, 0.2, 'sine', 0.15, 0.12);
  }

  playClick() {
    this.playTone(800, 0.03, 'square', 0.05, 0);
  }

  playScanLock() {
    this.playTone(880, 0.08, 'sawtooth', 0.2, 0);
    this.playTone(1760, 0.25, 'sine', 0.25, 0.06);
  }

  toggleMute() {
    this.muted = !this.muted;
    localStorage.setItem('sound_muted', this.muted);
    return this.muted;
  }
}

const sfx = new SoundFX();

// --- Main App State Manager ---
const AppState = {
  profile: null,
  consumed: null,
  meals: [],
  quests: [],
  foodCatalog: [],
  selectedFood: null,
  healthAdvisor: null,
  selectedAttentDose: 20,
  networkIp: '127.0.0.1',
  port: 8080,

  async init() {
    // Setup Service Worker
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/service-worker.js').catch(console.error);
    }

    // Load sound toggle state
    this.updateSoundBtnUI();

    // Check cached profile for immediate offline display
    const cachedProfile = localStorage.getItem('hunter_profile');
    if (cachedProfile) {
      try {
        this.profile = JSON.parse(cachedProfile);
        this.renderProfile();
      } catch (e) {}
    }

    const cachedHA = localStorage.getItem('hunter_health_advisor');
    if (cachedHA) {
      try {
        this.healthAdvisor = JSON.parse(cachedHA);
      } catch (e) {}
    }

    // Fetch live data from server
    await this.fetchNetworkInfo();
    await this.fetchTodayData();
    await this.fetchFoods();

    // Setup input listeners
    this.bindEvents();

    // System chime on launch
    setTimeout(() => {
      sfx.playSystemNotification();
    }, 400);
  },

  async fetchNetworkInfo() {
    try {
      const res = await fetch('/api/network-ip');
      const data = await res.json();
      this.networkIp = data.ip;
      this.port = data.port;
      document.getElementById('lan-ip-display').innerText = `http://${this.networkIp}:${this.port}`;
      document.getElementById('watch-url-display').innerText = `http://${this.networkIp}:${this.port}/watch`;
    } catch (e) {
      console.warn('Network IP fetch failed:', e);
    }
  },

  async fetchTodayData() {
    try {
      const res = await fetch('/api/nutrition/today');
      if (!res.ok) throw new Error('API error');
      const data = await res.json();
      this.profile = data.profile;
      this.consumed = data.consumed;
      this.meals = data.meals;
      this.quests = data.quests;
      this.shiftInfo = data.shift_info;
      if (data.health_advisor) {
        this.healthAdvisor = data.health_advisor;
        localStorage.setItem('hunter_health_advisor', JSON.stringify(this.healthAdvisor));
      }

      // Save to localStorage
      localStorage.setItem('hunter_profile', JSON.stringify(this.profile));
      localStorage.setItem('hunter_consumed', JSON.stringify(this.consumed));

      this.renderAll();
    } catch (err) {
      console.warn('Using offline cache:', err);
      const cachedC = localStorage.getItem('hunter_consumed');
      if (cachedC) this.consumed = JSON.parse(cachedC);
      const cachedHA = localStorage.getItem('hunter_health_advisor');
      if (cachedHA) this.healthAdvisor = JSON.parse(cachedHA);
      this.renderAll();
    }
  },

  async fetchFoods(search = '') {
    try {
      const res = await fetch(`/api/foods?q=${encodeURIComponent(search)}`);
      if (res.ok) {
        this.foodCatalog = await res.json();
      }
    } catch (e) {
      console.warn('Could not fetch foods:', e);
    }
  },

  // --- Rendering UI ---
  renderAll() {
    this.renderProfile();
    this.renderGarminBiometrics();
    this.renderAttentBanner();
    this.renderAIInsights();
    this.renderCalorieGauge();
    this.renderMacroBars();
    this.renderQuests();
    this.renderMicronutrients();
    this.renderMealsList();
  },

  renderProfile() {
    if (!this.profile) return;
    const p = this.profile;

    document.getElementById('hunter-name').innerText = p.name || 'צייד רום';
    document.getElementById('hunter-title').innerText = p.title || 'Awakened Hunter';
    document.getElementById('hunter-level').innerText = p.level;

    const rankBadge = document.getElementById('rank-badge');
    rankBadge.innerText = p.rank;
    rankBadge.className = 'rank-badge';
    if (p.level >= 75) {
      rankBadge.classList.add('shadow-monarch');
    } else if (p.level >= 50) {
      rankBadge.classList.add('s-rank');
    }

    // Shift Worker HUD Elements
    const isNight = (this.shiftInfo && this.shiftInfo.is_night) || (p.shift_mode === 'night');
    const shiftBtn = document.getElementById('shift-toggle-btn');
    if (shiftBtn) {
      shiftBtn.innerText = isNight ? '🌙' : '☀️';
      shiftBtn.title = isNight ? 'משמרת לילה פעילה (איפוס 08:00) - לחץ למעבר למשמרת יום' : 'משמרת יום פעילה (איפוס בחצות) - לחץ למעבר למשמרת לילה';
    }

    const shiftBadge = document.getElementById('shift-badge');
    const hoursLeft = this.shiftInfo ? this.shiftInfo.hours_left : (isNight ? 8 : 12);
    if (shiftBadge) {
      shiftBadge.innerText = isNight ? `🌙 משמרת לילה (${hoursLeft}h לסיום)` : `☀️ משמרת יום (${hoursLeft}h לסיום)`;
      shiftBadge.style.borderColor = isNight ? 'var(--neon-purple)' : '#3b82f6';
      shiftBadge.style.background = isNight ? 'rgba(147, 51, 234, 0.2)' : 'rgba(59, 130, 246, 0.15)';
      shiftBadge.style.color = isNight ? '#d8b4fe' : '#93c5fd';
    }

    const penaltyText = document.getElementById('penalty-warning-text');
    const resetH = this.shiftInfo ? this.shiftInfo.day_reset_hour : (isNight ? 8 : 0);
    if (penaltyText) {
      penaltyText.innerText = isNight
        ? `אזהרת מערכת: נותרו ${hoursLeft} שעות עד סיום משמרת הלילה (${String(resetH).padStart(2, '0')}:00 בבוקר)!`
        : `אזהרת מערכת: נותרו ${hoursLeft} שעות עד חצות!`;
    }

    // Big Hero Shift Banner
    const shiftBanner = document.getElementById('shift-banner');
    const bannerIcon = document.getElementById('shift-banner-icon');
    const bannerTitle = document.getElementById('shift-banner-title');
    const bannerSub = document.getElementById('shift-banner-sub');
    const actionBtn = document.getElementById('shift-action-text-btn');

    if (shiftBanner && bannerIcon && bannerTitle && bannerSub && actionBtn) {
      if (isNight) {
        shiftBanner.classList.add('night-active');
        bannerIcon.innerText = '🌙';
        bannerTitle.innerText = `משמרת לילה פעילה (איפוס ב-${String(resetH).padStart(2, '0')}:00 בבוקר)`;
        bannerSub.innerText = `היום לא מתאפס בחצות! נותרו ${hoursLeft} שעות לסיום המשמרת`;
        actionBtn.innerText = 'החלף למשמרת יום ☀️';
      } else {
        shiftBanner.classList.remove('night-active');
        bannerIcon.innerText = '☀️';
        bannerTitle.innerText = 'משמרת יום רגילה (איפוס בחצות 00:00)';
        bannerSub.innerText = 'עובד הלילה? לחץ כאן להפעלת משמרת לילה 🌙 (היום לא יתאפס בחצות!)';
        actionBtn.innerText = 'הפעל משמרת לילה 🌙';
      }
    }

    // Dynamic Shift Meal Options
    const mealSelect = document.getElementById('meal-type-select');
    if (mealSelect) {
      const curVal = mealSelect.value;
      if (isNight) {
        mealSelect.innerHTML = `
          <option value="pre_shift">ארוחה לפני משמרת (Pre-Shift)</option>
          <option value="mid_shift" selected>אמצע משמרת (01:00-03:00)</option>
          <option value="post_shift">סיום משמרת (07:00)</option>
          <option value="shift_snack">נשנוש פוקוס וערנות</option>
        `;
      } else {
        mealSelect.innerHTML = `
          <option value="breakfast">ארוחת בוקר</option>
          <option value="lunch" selected>ארוחת צהריים</option>
          <option value="dinner">ארוחת ערב</option>
          <option value="snack">נשנוש / אימון</option>
        `;
      }
      if (mealSelect.querySelector(`option[value="${curVal}"]`)) {
        mealSelect.value = curVal;
      }
    }

    // EXP Bar
    const expPct = Math.min(100, Math.round((p.exp / Math.max(1, p.exp_to_next)) * 100));
    document.getElementById('exp-bar-fill').style.width = `${expPct}%`;
    document.getElementById('exp-text').innerText = `${p.exp} / ${p.exp_to_next} EXP (${expPct}%)`;

    // Status Attributes (STR, AGI, VIT, INT, PER)
    document.getElementById('stat-str').innerText = p.stats_str;
    document.getElementById('stat-agi').innerText = p.stats_agi;
    document.getElementById('stat-vit').innerText = p.stats_vit;
    document.getElementById('stat-int').innerText = p.stats_int;
    document.getElementById('stat-per').innerText = p.stats_per;

    // Fatigue
    const fatigueEl = document.getElementById('fatigue-val');
    if (fatigueEl) {
      fatigueEl.innerText = `${p.fatigue}%`;
      fatigueEl.style.color = p.fatigue > 50 ? 'var(--neon-red)' : 'var(--hud-cyan)';
    }
  },

  renderCalorieGauge() {
    if (!this.profile || !this.consumed) return;
    const target = this.healthAdvisor?.effective_target_calories || this.profile.target_calories;
    const current = Math.round(this.consumed.calories);
    const remaining = Math.max(0, target - current);

    document.getElementById('cal-current').innerText = current;
    const activeBurn = this.healthAdvisor?.biometrics?.active_calories || 0;
    if (activeBurn > 0) {
      document.getElementById('cal-target').innerHTML = `${target} kcal <span style="font-size:10px; color:#10b981;">(+${activeBurn} Garmin)</span>`;
    } else {
      document.getElementById('cal-target').innerText = `${target} kcal`;
    }
    document.getElementById('cal-remaining').innerText = `${remaining} kcal`;

    // SVG circle circumference = 2 * PI * r = 2 * 3.14159 * 60 ≈ 377
    const circumference = 377;
    const pct = Math.min(1, current / Math.max(1, target));
    const offset = circumference - (pct * circumference);
    const gaugeEl = document.getElementById('calorie-gauge-bar');
    if (gaugeEl) {
      gaugeEl.style.strokeDashoffset = offset;
    }
  },

  renderMacroBars() {
    if (!this.profile || !this.consumed) return;
    const p = this.profile;
    const c = this.consumed;

    // Protein
    const protCurrent = Math.round(c.protein);
    const protTarget = p.target_protein;
    const protPct = Math.min(100, Math.round((protCurrent / Math.max(1, protTarget)) * 100));
    document.getElementById('macro-protein-cur').innerText = `${protCurrent}g`;
    document.getElementById('macro-protein-tgt').innerText = `/ ${protTarget}g`;
    document.getElementById('macro-protein-bar').style.width = `${protPct}%`;

    // Carbs
    const carbsCurrent = Math.round(c.carbs);
    const carbsTarget = p.target_carbs;
    const carbsPct = Math.min(100, Math.round((carbsCurrent / Math.max(1, carbsTarget)) * 100));
    document.getElementById('macro-carbs-cur').innerText = `${carbsCurrent}g`;
    document.getElementById('macro-carbs-tgt').innerText = `/ ${carbsTarget}g`;
    document.getElementById('macro-carbs-bar').style.width = `${carbsPct}%`;

    // Fats
    const fatsCurrent = Math.round(c.fats);
    const fatsTarget = p.target_fats;
    const fatsPct = Math.min(100, Math.round((fatsCurrent / Math.max(1, fatsTarget)) * 100));
    document.getElementById('macro-fats-cur').innerText = `${fatsCurrent}g`;
    document.getElementById('macro-fats-tgt').innerText = `/ ${fatsTarget}g`;
    document.getElementById('macro-fats-bar').style.width = `${fatsPct}%`;
  },

  renderQuests() {
    const listEl = document.getElementById('quest-list');
    if (!listEl || !this.quests) return;

    listEl.innerHTML = '';
    this.quests.forEach(q => {
      const row = document.createElement('div');
      row.className = `quest-row ${q.done ? 'done' : ''}`;
      row.innerHTML = `
        <div class="quest-info">
          <span class="quest-name">${q.title}</span>
          <span class="quest-progress-txt">${q.desc} (${q.current} / ${q.target} ${q.unit})</span>
        </div>
        <div class="quest-check">${q.done ? '✓' : '○'}</div>
      `;
      listEl.appendChild(row);
    });
  },

  renderMicronutrients() {
    if (!this.profile || !this.consumed) return;
    const c = this.consumed;
    const p = this.profile;

    const micros = [
      { name: 'מים (רוויה)', cur: c.water_ml, tgt: p.target_water, unit: 'ml' },
      { name: 'סיבים תזונתיים', cur: Math.round(c.fiber), tgt: p.target_fiber, unit: 'g' },
      { name: 'מגנזיום (התאוששות)', cur: Math.round(c.magnesium_mg), tgt: 400, unit: 'mg' },
      { name: 'אבץ (מערכת חיסון)', cur: Math.round(c.zinc_mg), tgt: 14, unit: 'mg' },
      { name: 'ויטמין C', cur: Math.round(c.vit_c_mg), tgt: 90, unit: 'mg' },
      { name: 'אשלגן (אלקטרוליטים)', cur: Math.round(c.potassium_mg), tgt: 3500, unit: 'mg' }
    ];

    const gridEl = document.getElementById('micro-grid');
    if (!gridEl) return;
    gridEl.innerHTML = '';

    micros.forEach(m => {
      const pct = Math.min(100, Math.round((m.cur / Math.max(1, m.tgt)) * 100));
      const item = document.createElement('div');
      item.className = 'micro-item';
      item.innerHTML = `
        <div class="micro-top">
          <span class="micro-name">${m.name}</span>
          <span class="micro-vals">${m.cur}/${m.tgt} ${m.unit} (${pct}%)</span>
        </div>
        <div class="micro-track">
          <div class="micro-fill" style="width: ${pct}%"></div>
        </div>
      `;
      gridEl.appendChild(item);
    });
  },

  renderMealsList() {
    const listEl = document.getElementById('meals-history-list');
    if (!listEl) return;

    if (!this.meals || this.meals.length === 0) {
      listEl.innerHTML = `<div style="text-align:center; padding: 14px; font-size: 12px; color: var(--text-dim);">טרם נרשמו ארוחות היום. בחר מזון למעלה או השתמש בשיקויי האינוונטר!</div>`;
      return;
    }

    listEl.innerHTML = '';
    this.meals.forEach(m => {
      const entry = document.createElement('div');
      entry.className = 'meal-entry';
      entry.innerHTML = `
        <div class="meal-entry-info">
          <div class="meal-entry-name">${m.food_name} <span style="font-size:10px; color:var(--hud-cyan); font-family:var(--font-mono);">${m.timestamp || ''}</span></div>
          <div class="meal-entry-macros">
            ${Math.round(m.calories)} קלוריות | חלבון: ${Math.round(m.protein)}g | פחמימה: ${Math.round(m.carbs)}g | שומן: ${Math.round(m.fats)}g
          </div>
        </div>
        <button class="meal-delete-btn" onclick="AppState.deleteMeal(${m.id})" title="מחק ארוחה">✕</button>
      `;
      listEl.appendChild(entry);
    });
  },

  // --- Actions & API Calls ---
  async deleteMeal(id) {
    if (!confirm('האם למחוק ארוחה זו מהיומן?')) return;
    sfx.playClick();
    try {
      await fetch(`/api/nutrition/log/${id}`, { method: 'DELETE' });
      await this.fetchTodayData();
    } catch (e) {
      alert('שגיאה במחיקת הארוחה');
    }
  },

  async logQuickPotion(potionType) {
    sfx.playPotion();
    try {
      const res = await fetch('/api/nutrition/quick-potion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ potion_type: potionType })
      });
      const data = await res.json();
      if (data.leveling && data.leveling.leveled_up) {
        this.showLevelUpModal(data.leveling);
      }
      await this.fetchTodayData();
    } catch (e) {
      console.error(e);
    }
  },

  async logSelectedFood() {
    if (!this.selectedFood) return;
    sfx.playClick();
    const grams = parseFloat(document.getElementById('portion-grams-input').value) || 100;
    const factor = grams / (this.selectedFood.serving_size_g || 100);
    const mealType = document.getElementById('meal-type-select').value;

    const payload = {
      food_id: this.selectedFood.id,
      food_name: this.selectedFood.name_he || this.selectedFood.name,
      serving_count: factor,
      serving_size_g: grams,
      calories: this.selectedFood.calories,
      protein: this.selectedFood.protein,
      carbs: this.selectedFood.carbs,
      fats: this.selectedFood.fats,
      fiber: this.selectedFood.fiber || 0,
      sodium_mg: this.selectedFood.sodium_mg || 0,
      potassium_mg: this.selectedFood.potassium_mg || 0,
      magnesium_mg: this.selectedFood.magnesium_mg || 0,
      zinc_mg: this.selectedFood.zinc_mg || 0,
      vit_c_mg: this.selectedFood.vit_c_mg || 0,
      vit_d_iu: this.selectedFood.vit_d_iu || 0,
      iron_mg: this.selectedFood.iron_mg || 0,
      meal_type: mealType
    };

    try {
      const res = await fetch('/api/nutrition/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      // Reset selection
      this.selectedFood = null;
      document.getElementById('staging-card').style.display = 'none';
      document.getElementById('food-search-input').value = '';

      if (data.leveling && data.leveling.leveled_up) {
        this.showLevelUpModal(data.leveling);
      } else {
        sfx.playSystemNotification();
      }

      await this.fetchTodayData();
    } catch (e) {
      alert('שגיאה ברישום הארוחה');
    }
  },

  showLevelUpModal(lvlData) {
    sfx.playLevelUp();
    const modal = document.getElementById('levelup-overlay');
    document.getElementById('levelup-level-val').innerText = lvlData.level;
    document.getElementById('levelup-rank-val').innerText = lvlData.rank;
    modal.classList.add('active');

    setTimeout(() => {
      modal.classList.remove('active');
    }, 3500);
  },

  updateSoundBtnUI() {
    const btn = document.getElementById('sound-toggle-btn');
    if (btn) {
      btn.innerText = sfx.muted ? '🔇' : '🔊';
    }
  },

  // --- Event Bindings ---
  bindEvents() {
    // Sound toggle
    const soundBtn = document.getElementById('sound-toggle-btn');
    if (soundBtn) {
      soundBtn.addEventListener('click', () => {
        const isMuted = sfx.toggleMute();
        this.updateSoundBtnUI();
        if (!isMuted) sfx.playSystemNotification();
      });
    }

    // Food search input
    const searchInput = document.getElementById('food-search-input');
    const resultsContainer = document.getElementById('food-search-results');

    searchInput.addEventListener('input', (e) => {
      const val = e.target.value.toLowerCase().trim();
      if (!val) {
        resultsContainer.style.display = 'none';
        return;
      }

      const matches = this.foodCatalog.filter(f => 
        (f.name_he && f.name_he.toLowerCase().includes(val)) ||
        (f.name && f.name.toLowerCase().includes(val))
      );

      if (matches.length === 0) {
        resultsContainer.innerHTML = `<div style="padding:10px; font-size:12px; color:var(--text-dim);">לא נמצאו תוצאות. תוכל להוסיף מזון מותאם בהגדרות.</div>`;
      } else {
        resultsContainer.innerHTML = '';
        matches.slice(0, 10).forEach(item => {
          const div = document.createElement('div');
          div.className = 'food-result-item';
          div.innerHTML = `
            <span class="food-res-name">${item.name_he || item.name}</span>
            <span class="food-res-meta">${item.calories} קלוריות | P: ${item.protein}g</span>
          `;
          div.addEventListener('click', () => {
            this.selectFood(item);
            resultsContainer.style.display = 'none';
          });
          resultsContainer.appendChild(div);
        });
      }
      resultsContainer.style.display = 'flex';
    });

    // Close search dropdown on click outside
    document.addEventListener('click', (e) => {
      if (!searchInput.contains(e.target) && !resultsContainer.contains(e.target)) {
        resultsContainer.style.display = 'none';
      }
    });

    // Awakening modal dynamic preview calculation
    ['awakening-weight', 'awakening-height', 'awakening-age', 'awakening-activity', 'awakening-goal', 'awakening-sex'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', () => this.updateAwakeningPreview());
    });
  },

  selectFood(item) {
    sfx.playClick();
    this.selectedFood = item;
    const staging = document.getElementById('staging-card');
    document.getElementById('staging-name').innerText = item.name_he || item.name;
    document.getElementById('portion-grams-input').value = item.serving_size_g || 100;
    staging.style.display = 'flex';
  },

  // Awakening Scientific Assessment Logic
  updateAwakeningPreview() {
    const weight = parseFloat(document.getElementById('awakening-weight').value) || 75;
    const height = parseFloat(document.getElementById('awakening-height').value) || 175;
    const age = parseInt(document.getElementById('awakening-age').value) || 25;
    const sex = document.getElementById('awakening-sex').value;
    const activity = document.getElementById('awakening-activity').value;
    const goal = document.getElementById('awakening-goal').value;

    // BMR (Mifflin-St Jeor)
    let bmr = (10 * weight) + (6.25 * height) - (5 * age);
    bmr += (sex === 'female' ? -161 : 5);

    const mults = { sedentary: 1.2, light: 1.375, moderate: 1.55, very_active: 1.725, extra_active: 1.9 };
    const tdee = Math.round(bmr * (mults[activity] || 1.55));

    let cals = tdee;
    let protFactor = 1.9;
    if (goal === 'cut') {
      cals = Math.round(tdee * 0.8);
      protFactor = 2.2;
    } else if (goal === 'bulk') {
      cals = Math.round(tdee * 1.09);
      protFactor = 1.9;
    }

    const protein = Math.round(weight * protFactor);
    const fats = Math.max(45, Math.round(weight * 0.85));
    const carbs = Math.max(50, Math.round((cals - (protein * 4) - (fats * 9)) / 4));
    const water = Math.round(weight * 38 + 500);

    document.getElementById('prev-bmr').innerText = `${Math.round(bmr)} kcal`;
    document.getElementById('prev-tdee').innerText = `${tdee} kcal`;
    document.getElementById('prev-target-cals').innerText = `${cals} kcal`;
    document.getElementById('prev-protein').innerText = `${protein}g (${Math.round((protein*4/cals)*100)}%)`;
    document.getElementById('prev-carbs').innerText = `${carbs}g (${Math.round((carbs*4/cals)*100)}%)`;
    document.getElementById('prev-fats').innerText = `${fats}g (${Math.round((fats*9/cals)*100)}%)`;
    document.getElementById('prev-water').innerText = `${water} ml`;
  },

  async submitAwakening() {
    sfx.playClick();
    const payload = {
      name: document.getElementById('awakening-name').value || 'צייד רום',
      weight: parseFloat(document.getElementById('awakening-weight').value) || 78,
      height: parseFloat(document.getElementById('awakening-height').value) || 178,
      age: parseInt(document.getElementById('awakening-age').value) || 25,
      sex: document.getElementById('awakening-sex').value,
      activity_level: document.getElementById('awakening-activity').value,
      goal: document.getElementById('awakening-goal').value
    };

    try {
      const res = await fetch('/api/awakening', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      this.closeModal('awakening-modal');
      sfx.playLevelUp();
      alert('ההתעוררות הושלמה בהצלחה! יעדי התזונה המדעיים עודכנו.');
      await this.fetchTodayData();
    } catch (e) {
      alert('שגיאה בחישוב ההתעוררות');
    }
  },

  // Modal helpers
  openModal(id) {
    sfx.playClick();
    const m = document.getElementById(id);
    if (m) {
      m.style.display = 'flex';
      if (id === 'awakening-modal') {
        this.updateAwakeningPreview();
      }
    }
  },

  closeModal(id) {
    sfx.playClick();
    const m = document.getElementById(id);
    if (m) m.style.display = 'none';
  },

  // Export JSON Backup
  async exportBackup() {
    sfx.playClick();
    window.location.href = '/api/backup';
  },

  // Open watch simulator in new tab
  openWatchSimulator() {
    sfx.playClick();
    window.open('/watch', '_blank');
  },

  // --- Barcode Scanner Logic ---
  videoStream: null,
  scannerInterval: null,

  async openBarcodeScanner() {
    sfx.playClick();
    this.openModal('barcode-modal');
    const statusEl = document.getElementById('scanner-status');
    const video = document.getElementById('scanner-video');
    const cameraInput = document.getElementById('barcode-camera-input');

    if (cameraInput) cameraInput.value = '';

    const hasMedia = navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function';

    if (hasMedia) {
      statusEl.innerText = '[SYSTEM: מפעיל חיישני זיהוי ומצלמה...]';
      try {
        this.videoStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }
        });
        video.srcObject = this.videoStream;
        await video.play();
        statusEl.innerText = '[SYSTEM: כוון אל מרכז הברקוד...]';

        if ('BarcodeDetector' in window) {
          const detector = new BarcodeDetector({
            formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'qr_code']
          });

          this.scannerInterval = setInterval(async () => {
            try {
              const barcodes = await detector.detect(video);
              if (barcodes.length > 0) {
                const detectedCode = barcodes[0].rawValue;
                clearInterval(this.scannerInterval);
                this.scannerInterval = null;
                this.lookupBarcode(detectedCode);
              }
            } catch (err) {}
          }, 250);
        } else {
          statusEl.innerText = '[SYSTEM: סורק פעיל - כוון למרכז או צלם בכפתור הכחול]';
        }
      } catch (err) {
        console.warn('Live camera access error:', err);
        statusEl.innerText = '📱 מצלמת וידאו חיה דורשת אישור. לחץ על הכפתור הכחול לצילום ישיר במצלמת האייפון!';
      }
    } else {
      // In iOS Safari over HTTP: direct camera capture is active
      statusEl.innerText = '📱 לחץ על הכפתור הכחול למעלה לפתיחת מצלמת האייפון וצילום הברקוד!';
      // Automatically prompt native camera on mobile device
      const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
      if (isMobile && cameraInput) {
        setTimeout(() => {
          cameraInput.click();
        }, 200);
      }
    }
  },

  async handleCameraPhoto(input) {
    const file = input.files && input.files[0];
    if (!file) return;

    sfx.playClick();
    const statusEl = document.getElementById('scanner-status');
    statusEl.innerText = '[SYSTEM: מעבד ומפענח תמונת ברקוד...]';

    const reader = new FileReader();
    reader.onload = async (e) => {
      const img = new Image();
      img.onload = async () => {
        // Draw to canvas with optimal resolution for sharp barcode recognition
        const canvas = document.createElement('canvas');
        let width = img.width;
        let height = img.height;
        const maxDim = 1280;
        if (width > maxDim || height > maxDim) {
          if (width > height) {
            height = Math.round((height * maxDim) / width);
            width = maxDim;
          } else {
            width = Math.round((width * maxDim) / height);
            height = maxDim;
          }
        }
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);

        // 1. Try Native BarcodeDetector (iOS 17+ / Chrome)
        if ('BarcodeDetector' in window) {
          try {
            const detector = new BarcodeDetector({
              formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39', 'qr_code']
            });
            const barcodes = await detector.detect(canvas);
            if (barcodes && barcodes.length > 0) {
              const code = barcodes[0].rawValue;
              statusEl.innerText = `[✓ זוהה ברקוד: ${code}]`;
              sfx.playScanLock();
              this.lookupBarcode(code);
              return;
            }
          } catch (err) {
            console.warn('BarcodeDetector on photo error:', err);
          }
        }

        // 2. Pure JavaScript 1D Barcode Scanner Fallback (EAN-13 & UPC)
        const decoded = this.scan1DBarcodeFromCanvas(canvas);
        if (decoded) {
          statusEl.innerText = `[✓ זוהה ברקוד: ${decoded}]`;
          sfx.playScanLock();
          this.lookupBarcode(decoded);
          return;
        }

        statusEl.innerHTML = `
          <div style="color:#f87171; font-weight:700;">❌ לא זוהה ברקוד בבירור בתמונה</div>
          <div style="font-size:11px; color:#cbd5e1; margin-top:4px;">
            נסה לצלם שוב כשהברקוד מואר, קרוב וישר, או הקלד את המספר ידנית למטה.
          </div>
        `;
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  },

  scan1DBarcodeFromCanvas(canvas) {
    try {
      const ctx = canvas.getContext('2d');
      const width = canvas.width;
      const height = canvas.height;

      const L_PATTERNS = {
        '3,2,1,1': 0, '2,2,2,1': 1, '2,1,2,2': 2, '1,4,1,1': 3,
        '1,1,3,2': 4, '1,2,3,1': 5, '1,1,1,4': 6, '1,3,1,2': 7,
        '1,2,1,3': 8, '3,1,1,2': 9
      };
      const G_PATTERNS = {
        '1,1,2,3': 0, '1,2,2,2': 1, '2,2,1,2': 2, '1,1,4,1': 3,
        '2,3,1,1': 4, '1,3,2,1': 5, '4,1,1,1': 6, '2,1,3,1': 7,
        '3,1,2,1': 8, '2,1,1,3': 9
      };
      const FIRST_MAP = {
        'LLLLLL': 0, 'LLGLGG': 1, 'LLGGLG': 2, 'LLGGGL': 3, 'LGLLGG': 4,
        'LGGLLG': 5, 'LGGGLL': 6, 'LGLGLG': 7, 'LGLGGL': 8, 'LGGLGL': 9
      };

      // Sample 30 horizontal scanlines across vertical center
      for (let s = 4; s <= 26; s++) {
        const y = Math.floor(height * (s / 30));
        const row = ctx.getImageData(0, y, width, 1).data;

        const lums = new Float32Array(width);
        let sumLum = 0;
        for (let x = 0; x < width; x++) {
          const idx = x * 4;
          const lum = row[idx] * 0.299 + row[idx + 1] * 0.587 + row[idx + 2] * 0.114;
          lums[x] = lum;
          sumLum += lum;
        }
        const avg = sumLum / width;

        const runs = [];
        let curIsDark = lums[0] < avg;
        let curLen = 0;
        for (let x = 0; x < width; x++) {
          const isDark = lums[x] < avg;
          if (isDark === curIsDark) {
            curLen++;
          } else {
            runs.push({ isDark: curIsDark, len: curLen });
            curIsDark = isDark;
            curLen = 1;
          }
        }
        runs.push({ isDark: curIsDark, len: curLen });

        for (let i = 0; i <= runs.length - 59; i++) {
          if (!runs[i].isDark || runs[i + 1].isDark || !runs[i + 2].isDark) continue;
          const w = (runs[i].len + runs[i + 1].len + runs[i + 2].len) / 3.0;
          if (w < 1) continue;

          if (runs[i + 27].isDark || !runs[i + 28].isDark || runs[i + 29].isDark || !runs[i + 30].isDark || runs[i + 31].isDark) continue;
          if (!runs[i + 56].isDark || runs[i + 57].isDark || !runs[i + 58].isDark) continue;

          let leftDigits = [];
          let parityPattern = '';
          let validLeft = true;

          for (let d = 0; d < 6; d++) {
            const rIdx = i + 3 + (d * 4);
            const r0 = runs[rIdx].len;
            const r1 = runs[rIdx + 1].len;
            const r2 = runs[rIdx + 2].len;
            const r3 = runs[rIdx + 3].len;
            const dSum = r0 + r1 + r2 + r3;
            if (dSum === 0) { validLeft = false; break; }

            const n0 = Math.max(1, Math.round((r0 / dSum) * 7));
            const n1 = Math.max(1, Math.round((r1 / dSum) * 7));
            const n2 = Math.max(1, Math.round((r2 / dSum) * 7));
            const n3 = Math.max(1, Math.round((r3 / dSum) * 7));
            const key = `${n0},${n1},${n2},${n3}`;

            if (L_PATTERNS[key] !== undefined) {
              leftDigits.push(L_PATTERNS[key]);
              parityPattern += 'L';
            } else if (G_PATTERNS[key] !== undefined) {
              leftDigits.push(G_PATTERNS[key]);
              parityPattern += 'G';
            } else {
              validLeft = false;
              break;
            }
          }

          if (!validLeft || FIRST_MAP[parityPattern] === undefined) continue;
          const firstDigit = FIRST_MAP[parityPattern];

          let rightDigits = [];
          let validRight = true;
          for (let d = 0; d < 6; d++) {
            const rIdx = i + 32 + (d * 4);
            const r0 = runs[rIdx].len;
            const r1 = runs[rIdx + 1].len;
            const r2 = runs[rIdx + 2].len;
            const r3 = runs[rIdx + 3].len;
            const dSum = r0 + r1 + r2 + r3;
            if (dSum === 0) { validRight = false; break; }

            const n0 = Math.max(1, Math.round((r0 / dSum) * 7));
            const n1 = Math.max(1, Math.round((r1 / dSum) * 7));
            const n2 = Math.max(1, Math.round((r2 / dSum) * 7));
            const n3 = Math.max(1, Math.round((r3 / dSum) * 7));
            const key = `${n0},${n1},${n2},${n3}`;

            if (L_PATTERNS[key] !== undefined) {
              rightDigits.push(L_PATTERNS[key]);
            } else {
              validRight = false;
              break;
            }
          }

          if (!validRight) continue;

          const allDigits = [firstDigit, ...leftDigits, ...rightDigits];
          let chkSum = 0;
          for (let k = 0; k < 12; k++) {
            chkSum += (k % 2 === 0) ? allDigits[k] : allDigits[k] * 3;
          }
          const expectedCheck = (10 - (chkSum % 10)) % 10;
          if (expectedCheck === allDigits[12]) {
            return allDigits.join('');
          }
        }
      }
    } catch (e) {
      console.warn('1D Barcode decode error:', e);
    }
    return null;
  },

  closeBarcodeScanner() {
    if (this.videoStream) {
      this.videoStream.getTracks().forEach(track => track.stop());
      this.videoStream = null;
    }
    if (this.scannerInterval) {
      clearInterval(this.scannerInterval);
      this.scannerInterval = null;
    }
    const video = document.getElementById('scanner-video');
    if (video) video.srcObject = null;
    this.closeModal('barcode-modal');
  },

  submitManualBarcode() {
    const input = document.getElementById('manual-barcode-input');
    const val = input.value.trim();
    if (val) {
      this.lookupBarcode(val);
    }
  },

  async lookupBarcode(barcode) {
    sfx.playScanLock();
    const statusEl = document.getElementById('scanner-status');
    statusEl.innerText = `[SYSTEM: מאתר חתימת ברקוד ${barcode}...]`;

    let item = null;

    // 1. Try local database first
    try {
      const res = await fetch(`/api/barcode/${encodeURIComponent(barcode)}`);
      if (res.ok) {
        const data = await res.json();
        item = data.item;
      }
    } catch (e) {
      console.warn('Local barcode lookup failed:', e);
    }

    // 2. Client-side fallback to Open Food Facts API (direct from browser)
    if (!item) {
      try {
        const offRes = await fetch(`https://world.openfoodfacts.org/api/v0/product/${barcode}.json`);
        if (offRes.ok) {
          const offData = await offRes.json();
          if (offData.status === 1 && offData.product) {
            const p = offData.product;
            const nutriments = p.nutriments || {};
            item = {
              name: p.product_name || p.product_name_en || 'מוצר סרוק',
              name_he: p.product_name_he || p.product_name || p.product_name_en || 'מוצר סרוק',
              serving_size_g: 100,
              calories: parseFloat(nutriments['energy-kcal_100g'] || nutriments['energy-kcal'] || 0),
              protein: parseFloat(nutriments['proteins_100g'] || nutriments['proteins'] || 0),
              carbs: parseFloat(nutriments['carbohydrates_100g'] || nutriments['carbohydrates'] || 0),
              fats: parseFloat(nutriments['fat_100g'] || nutriments['fat'] || 0),
              fiber: parseFloat(nutriments['fiber_100g'] || nutriments['fiber'] || 0),
              sodium_mg: parseFloat(nutriments['sodium_100g'] || 0) * 1000
            };
          }
        }
      } catch (offErr) {
        console.warn('Open Food Facts client lookup error:', offErr);
      }
    }

    if (item) {
      document.getElementById('unknown-barcode-section').style.display = 'none';
      this.closeBarcodeScanner();
      this.selectFood(item);
      const staging = document.getElementById('staging-card');
      staging.style.border = '2px solid var(--neon-green)';
      staging.scrollIntoView({ behavior: 'smooth', block: 'center' });
      sfx.playSystemNotification();
    } else {
      this.lastUnknownBarcode = barcode;
      statusEl.innerText = `[SYSTEM: הברקוד ${barcode} טרם מופה במאגר העולמי]`;
      document.getElementById('unknown-barcode-section').style.display = 'block';
    }
  },

  lastUnknownBarcode: null,

  openNewProductModal() {
    sfx.playClick();
    document.getElementById('new-prod-barcode').value = this.lastUnknownBarcode || '';
    document.getElementById('new-prod-name').value = '';
    document.getElementById('new-prod-cal').value = '';
    document.getElementById('new-prod-protein').value = '';
    document.getElementById('new-prod-carbs').value = '';
    document.getElementById('new-prod-fats').value = '';
    this.openModal('new-product-modal');
  },

  async saveNewScannedProduct() {
    sfx.playClick();
    const name_he = document.getElementById('new-prod-name').value.trim();
    if (!name_he) {
      alert('נא להזין את שם המוצר');
      return;
    }
    const cal = parseFloat(document.getElementById('new-prod-cal').value) || 0;
    const protein = parseFloat(document.getElementById('new-prod-protein').value) || 0;
    const carbs = parseFloat(document.getElementById('new-prod-carbs').value) || 0;
    const fats = parseFloat(document.getElementById('new-prod-fats').value) || 0;

    const payload = {
      barcode: this.lastUnknownBarcode,
      name_he: name_he,
      name: name_he,
      serving_size_g: 100,
      calories: cal,
      protein: protein,
      carbs: carbs,
      fats: fats
    };

    try {
      const res = await fetch('/api/foods', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      const savedItem = data.item || payload;
      
      this.closeModal('new-product-modal');
      this.closeBarcodeScanner();
      
      // Select into staging card
      this.selectFood(savedItem);
      const staging = document.getElementById('staging-card');
      staging.style.border = '2px solid var(--neon-green)';
      staging.scrollIntoView({ behavior: 'smooth', block: 'center' });
      sfx.playSystemNotification();
      alert(`[✓ המוצר "${name_he}" נלמד ונשמר בהצלחה! בפעם הבאה שתסרוק אותו, הוא יזוהה מיידית]`);
      await this.fetchFoods();
    } catch (e) {
      alert('שגיאה בשמירת המוצר');
    }
  },

  // --- Shift Worker Controller ---
  async toggleShiftMode() {
    sfx.playClick();
    const curMode = (this.profile && this.profile.shift_mode) || 'standard';
    const newMode = curMode === 'night' ? 'standard' : 'night';
    const newResetHour = newMode === 'night' ? 8 : 0;

    try {
      const res = await fetch('/api/profile/shift-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shift_mode: newMode, day_reset_hour: newResetHour })
      });
      const data = await res.json();
      this.profile = data.profile;
      this.consumed = data.consumed;
      this.meals = data.meals;
      this.quests = data.quests;
      this.shiftInfo = data.shift_info;

      this.renderAll();
      sfx.playSystemNotification();
      if (newMode === 'night') {
        alert('[SYSTEM: הופעל מצב משמרת לילה! האיפוס היומי נדחה לשעה 08:00 בבוקר. כל הארוחות מרוכזות כיום רציף אחד ללא איפוס בחצות]');
      } else {
        alert('[SYSTEM: חזרה למשמרת יום רגילה (איפוס בחצות)]');
      }
    } catch (e) {
      alert('שגיאה בעדכון מצב המשמרת');
    }
  },

  async handleSettingsShiftChange() {
    sfx.playClick();
    const sel = document.getElementById('settings-shift-mode').value;
    const hourInput = document.getElementById('settings-reset-hour');
    let resetH = 0;
    if (sel === 'custom') {
      hourInput.style.display = 'inline-block';
      resetH = parseInt(hourInput.value) || 8;
    } else {
      hourInput.style.display = 'none';
      resetH = sel === 'night' ? 8 : 0;
    }

    try {
      const res = await fetch('/api/profile/shift-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shift_mode: sel, day_reset_hour: resetH })
      });
      const data = await res.json();
      this.profile = data.profile;
      this.consumed = data.consumed;
      this.meals = data.meals;
      this.quests = data.quests;
      this.shiftInfo = data.shift_info;
      this.renderAll();
      sfx.playSystemNotification();
    } catch (e) {
      console.warn('Shift change error:', e);
    }
  },

  // --- Garmin & Biometrics Controller ---
  renderGarminBiometrics() {
    if (!this.healthAdvisor || !this.healthAdvisor.biometrics) return;
    const b = this.healthAdvisor.biometrics;

    const hrEl = document.getElementById('garmin-hr-val');
    if (hrEl) hrEl.innerText = b.heart_rate || 68;
    const rhrEl = document.getElementById('garmin-resting-hr');
    if (rhrEl) rhrEl.innerText = `מנוחה: ${b.resting_hr || 58} bpm`;

    const sleepEl = document.getElementById('garmin-sleep-val');
    if (sleepEl) sleepEl.innerText = b.sleep_score || 82;
    const sleepHEl = document.getElementById('garmin-sleep-hours');
    if (sleepHEl) sleepHEl.innerText = `${b.sleep_hours || 7.2} שעות שינה`;

    const stressEl = document.getElementById('garmin-stress-val');
    if (stressEl) stressEl.innerText = b.stress_level || 28;
    const stressStatEl = document.getElementById('garmin-stress-status');
    if (stressStatEl) {
      const s = b.stress_level || 28;
      stressStatEl.innerText = s < 25 ? 'מנוחה (נמוך)' : (s < 50 ? 'נמוך-בינוני' : (s < 75 ? 'בינוני' : 'גבוה'));
    }

    const bbEl = document.getElementById('garmin-battery-val');
    if (bbEl) bbEl.innerText = `${b.body_battery || 75}%`;
    const bbStatEl = document.getElementById('garmin-battery-status');
    if (bbStatEl) {
      const bb = b.body_battery || 75;
      bbStatEl.innerText = bb > 70 ? 'אנרגיה טעונה' : (bb > 40 ? 'רמה בינונית' : 'מאגר נמוך');
    }

    const stepsEl = document.getElementById('garmin-steps-val');
    if (stepsEl) stepsEl.innerText = (b.steps || 8500).toLocaleString();
    const activeEl = document.getElementById('garmin-active-cals-val');
    if (activeEl) activeEl.innerText = `+${b.active_calories || 450}`;
    const spo2El = document.getElementById('garmin-spo2-val');
    if (spo2El) spo2El.innerText = `${b.spo2_pct || 98}%`;
  },

  renderAttentBanner() {
    const container = document.getElementById('attent-container');
    if (!container) return;
    const attent = this.healthAdvisor?.attent;

    if (attent && attent.is_active) {
      const dose = attent.dose_mg || 20;
      const elapsed = attent.elapsed_hours || 0;
      const rem = attent.remaining_hours || 0;
      const takenAt = attent.timestamp || '09:00';
      const pConsumed = Math.round(this.consumed?.protein || 0);
      const pTarget = this.profile?.target_protein || 160;

      container.innerHTML = `
        <div class="attent-buff-card">
          <div class="attent-header-row">
            <div class="attent-title-wrap">
              <span class="attent-pill-badge">💊</span>
              <div>
                <div class="attent-buff-title">BUFF פעיל: שיקוי ריכוז והיפר-פוקוס (Attent ${dose}mg)</div>
                <div class="attent-buff-sub">נלקח ב-${takenAt} • עברו ${elapsed.toFixed(1)} שעות • נותרו כ-${rem.toFixed(1)} שעות שיא</div>
              </div>
            </div>
            <button class="attent-cancel-btn" onclick="AppState.cancelAttent()" title="בטל רישום">✕ ביטול</button>
          </div>
          <div class="attent-badges-row">
            <span class="attent-badge-chip ${pConsumed < (pTarget * 0.5) ? 'alert' : 'success'}">
              🛡️ מגן שריר: ${pConsumed}g / ${pTarget}g חלבון
            </span>
            <span class="attent-badge-chip cyan">
              💧 יעד מים מוגבר (+500ml)
            </span>
            <span class="attent-badge-chip success">
              ⚡ סטרס Garmin מנוטרל
            </span>
          </div>
        </div>
      `;
    } else {
      container.innerHTML = `
        <div class="attent-prompt-card" onclick="AppState.openAttentModal()">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:18px;">💊</span>
            <div>
              <span style="font-size:12px; font-weight:700; color:#e9d5ff;">שיקוי ריכוז (אטנט / Attent)</span>
              <span style="font-size:10px; color:var(--text-secondary); display:block;">נטלת אטנט היום? לחץ כאן לרישום מהיר והפעלת מעקב AI</span>
            </div>
          </div>
          <button class="badge-button" style="background:rgba(168,85,247,0.25); border:1px solid #c084fc; color:#f3e8ff; font-size:11px; padding:4px 10px; border-radius:6px; cursor:pointer;">
            + רשום נטילה
          </button>
        </div>
      `;
    }
  },

  renderAIInsights() {
    const list = document.getElementById('ai-insights-list');
    if (!list) return;
    const insights = this.healthAdvisor?.insights || [];

    if (insights.length === 0) {
      list.innerHTML = `
        <div class="ai-insight-card info">
          <div class="ai-card-title">מערכת ה-AI מסנכרנת נתונים...</div>
          <div class="ai-card-message">רשום ארוחות ומדדי גרמין כדי לייצר תובנות פיזיולוגיות אישיות.</div>
        </div>
      `;
      return;
    }

    list.innerHTML = insights.map(ins => `
      <div class="ai-insight-card ${ins.level || 'info'} ${ins.category === 'attent' ? 'attent' : ''}">
        <div class="ai-card-top">
          <div class="ai-card-title-wrap">
            <span>${ins.icon || '⚡'}</span>
            <span class="ai-card-title">${ins.title}</span>
          </div>
          <span class="ai-card-tag">${ins.tag || 'AI ADVICE'}</span>
        </div>
        <div class="ai-card-message">${ins.message}</div>
        ${ins.action_text ? `<div class="ai-card-action">👉 ${ins.action_text}</div>` : ''}
      </div>
    `).join('');
  },

  openGarminModal() {
    sfx.playClick();
    if (this.healthAdvisor && this.healthAdvisor.biometrics) {
      const b = this.healthAdvisor.biometrics;
      document.getElementById('garmin-input-hr').value = b.heart_rate || 68;
      document.getElementById('garmin-input-rhr').value = b.resting_hr || 58;
      document.getElementById('garmin-input-sleep-score').value = b.sleep_score || 82;
      document.getElementById('garmin-input-sleep-hours').value = b.sleep_hours || 7.2;
      document.getElementById('garmin-input-stress').value = b.stress_level || 28;
      document.getElementById('garmin-input-bb').value = b.body_battery || 75;
      document.getElementById('garmin-input-steps').value = b.steps || 8500;
      document.getElementById('garmin-input-active-cals').value = b.active_calories || 450;
    }
    document.getElementById('garmin-modal').classList.add('active');
  },

  setGarminPreset(preset) {
    sfx.playClick();
    if (preset === 'rest') {
      document.getElementById('garmin-input-hr').value = 60;
      document.getElementById('garmin-input-rhr').value = 54;
      document.getElementById('garmin-input-sleep-score').value = 88;
      document.getElementById('garmin-input-sleep-hours').value = 8.1;
      document.getElementById('garmin-input-stress').value = 18;
      document.getElementById('garmin-input-bb').value = 90;
      document.getElementById('garmin-input-steps').value = 5200;
      document.getElementById('garmin-input-active-cals').value = 180;
    } else if (preset === 'workout') {
      document.getElementById('garmin-input-hr').value = 76;
      document.getElementById('garmin-input-rhr').value = 58;
      document.getElementById('garmin-input-sleep-score').value = 82;
      document.getElementById('garmin-input-sleep-hours').value = 7.2;
      document.getElementById('garmin-input-stress').value = 52;
      document.getElementById('garmin-input-bb').value = 65;
      document.getElementById('garmin-input-steps').value = 12500;
      document.getElementById('garmin-input-active-cals').value = 620;
    } else if (preset === 'deficit') {
      document.getElementById('garmin-input-hr').value = 78;
      document.getElementById('garmin-input-rhr').value = 64;
      document.getElementById('garmin-input-sleep-score').value = 54;
      document.getElementById('garmin-input-sleep-hours').value = 4.8;
      document.getElementById('garmin-input-stress').value = 62;
      document.getElementById('garmin-input-bb').value = 35;
      document.getElementById('garmin-input-steps').value = 7000;
      document.getElementById('garmin-input-active-cals').value = 300;
    }
  },

  async saveGarminHealth() {
    sfx.playClick();
    const payload = {
      heart_rate: parseInt(document.getElementById('garmin-input-hr').value) || 68,
      resting_hr: parseInt(document.getElementById('garmin-input-rhr').value) || 58,
      sleep_score: parseInt(document.getElementById('garmin-input-sleep-score').value) || 80,
      sleep_hours: parseFloat(document.getElementById('garmin-input-sleep-hours').value) || 7.0,
      stress_level: parseInt(document.getElementById('garmin-input-stress').value) || 28,
      body_battery: parseInt(document.getElementById('garmin-input-bb').value) || 75,
      steps: parseInt(document.getElementById('garmin-input-steps').value) || 8500,
      active_calories: parseInt(document.getElementById('garmin-input-active-cals').value) || 450
    };

    try {
      const res = await fetch('/api/garmin/health-sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.data) {
        this.healthAdvisor = data.data;
        this.renderAll();
        sfx.playSystemNotification();
        this.closeModal('garmin-modal');
      }
    } catch (e) {
      alert('שגיאה בסנכרון מדדי גרמין');
    }
  },

  openAttentModal() {
    sfx.playClick();
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const timeInput = document.getElementById('attent-input-time');
    if (timeInput) timeInput.value = `${hh}:${mm}`;

    this.selectAttentDose(this.selectedAttentDose || 20);

    const cancelWrap = document.getElementById('attent-active-cancel-wrap');
    if (cancelWrap) {
      const isActive = this.healthAdvisor?.attent?.is_active;
      cancelWrap.style.display = isActive ? 'block' : 'none';
    }

    document.getElementById('attent-modal').classList.add('active');
  },

  selectAttentDose(mg) {
    this.selectedAttentDose = mg;
    [10, 15, 20, 30].forEach(d => {
      const el = document.getElementById(`dose-pill-${d}`);
      if (el) {
        if (d === mg) el.classList.add('selected');
        else el.classList.remove('selected');
      }
    });
  },

  async saveAttentLog() {
    sfx.playClick();
    const dose = this.selectedAttentDose || 20;
    const timeVal = document.getElementById('attent-input-time').value || '09:00';
    const duration = parseFloat(document.getElementById('attent-input-duration').value) || 7.0;
    const notes = document.getElementById('attent-input-notes').value || 'שיקוי ריכוז והיפר-פוקוס';

    try {
      const res = await fetch('/api/medication/attent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dose_mg: dose,
          timestamp: timeVal,
          duration_hours: duration,
          notes: notes
        })
      });
      const data = await res.json();
      if (data.data) {
        this.healthAdvisor = data.data;
        this.renderAll();
        sfx.playPotion();
        this.closeModal('attent-modal');
        alert(`[SYSTEM: שיקוי ריכוז (אטנט ${dose}mg) הופעל בהצלחה! מנוע ה-AI הותאם לדיכוי תיאבון ולנטרול סטרס Garmin]`);
      }
    } catch (e) {
      alert('שגיאה ברישום נטילת אטנט');
    }
  },

  async cancelAttent() {
    sfx.playClick();
    if (!confirm('האם לבטל את רישום האטנט של היום?')) return;
    try {
      const res = await fetch('/api/medication/attent', { method: 'DELETE' });
      const data = await res.json();
      if (data.data) {
        this.healthAdvisor = data.data;
        this.renderAll();
        sfx.playSystemNotification();
        this.closeModal('attent-modal');
      }
    } catch (e) {
      alert('שגיאה בביטול רישום אטנט');
    }
  }
};

window.addEventListener('DOMContentLoaded', () => {
  AppState.init();
});
