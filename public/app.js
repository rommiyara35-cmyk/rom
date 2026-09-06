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
  skills: [],
  workouts: [],
  supplements: [],
  achievements: [],
  totalWorkouts: 0,
  achievementsSummary: null,
  dailyDebrief: null,
  activeDebriefTab: 'maintain',
  codeReader: null,

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

    const cachedAch = localStorage.getItem('hunter_achievements');
    if (cachedAch) {
      try {
        this.achievements = JSON.parse(cachedAch);
        this.renderAchievements();
      } catch (e) {}
    }

    // Fetch live data from server
    await this.fetchNetworkInfo();
    await this.fetchTodayData();
    await this.fetchAchievements();
    await this.fetchSkills();
    await this.fetchSupplements();
    await this.fetchDailyDebrief();
    await this.fetchFoods();
    await this.fetchLongTermInsights(14);

    // Setup input listeners
    this.bindEvents();

    // Check disaster recovery & auto snapshotting
    this.checkDisasterRecovery();
    this.saveLocalSnapshot();
    this.updateBackupUI();

    // Start Garmin Auto-Sync background heartbeat
    this.startGarminHeartbeat();

    // System chime on launch
    setTimeout(() => {
      sfx.playSystemNotification();
    }, 400);
  },

  startGarminHeartbeat() {
    if (this._garminHeartbeatInterval) return;
    this._garminHeartbeatInterval = setInterval(async () => {
      if (document.hidden) return;
      try {
        const res = await fetch('/api/garmin/health');
        if (res.ok) {
          const data = await res.json();
          if (data && data.biometrics) {
            const oldSync = this.healthAdvisor?.biometrics?.sync_timestamp;
            const newSync = data.biometrics.sync_timestamp;
            this.healthAdvisor = data;
            this.renderGarminBiometrics();
            if (oldSync && newSync && oldSync !== newSync) {
              sfx.playTone(880, 0.1, 'sine', 0.08);
            }
          }
        }
      } catch (e) {}
    }, 45000);
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
      if (data.total_workouts !== undefined) {
        this.totalWorkouts = data.total_workouts;
      }
      if (data.achievements_summary) {
        this.achievementsSummary = data.achievements_summary;
        this.updateBadgePills(data.achievements_summary.unlocked_count, data.achievements_summary.total_count);
      }
      if (data.health_advisor) {
        this.healthAdvisor = data.health_advisor;
        localStorage.setItem('hunter_health_advisor', JSON.stringify(this.healthAdvisor));
      }

      // Save to localStorage
      localStorage.setItem('hunter_profile', JSON.stringify(this.profile));
      localStorage.setItem('hunter_consumed', JSON.stringify(this.consumed));

      this.renderAll();
      this.triggerDebouncedSnapshot();
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
    this.renderSkills();
    this.renderSupplements();
    this.renderDailyDebrief();
    this.renderGarminBiometrics();
    this.renderAttentBanner();
    this.renderAIInsights();
    this.renderCalorieGauge();
    this.renderMacroBars();
    this.renderQuests();
    this.renderMicronutrients();
    this.renderMealsList();
    if (this.longTermData) this.renderLongTermInsights(this.longTermData);
  },

  renderProfile() {
    if (!this.profile) return;
    const p = this.profile;

    document.getElementById('hunter-name').innerText = p.name || 'צייד רום';
    document.getElementById('hunter-title').innerText = p.title || 'Awakened Hunter';
    document.getElementById('hunter-level').innerText = p.level;

    const topName = document.getElementById('top-hunter-name-display');
    if (topName) topName.innerText = p.name || 'צייד רום';
    const topLvl = document.getElementById('top-hunter-lvl-chip');
    if (topLvl) topLvl.innerText = `Lv. ${p.level}`;

    const rankBadge = document.getElementById('rank-badge');
    if (rankBadge) {
      const cleanRank = (p.rank || 'E-Rank').replace('-Rank', '').replace('Rank', '').trim();
      rankBadge.innerText = cleanRank;
      const rankKey = `rank-${cleanRank.toLowerCase()}`;
      rankBadge.className = `gauge-hex-inner ${rankKey}`;
    }

    const workoutsValEl = document.getElementById('gauge-workouts-val');
    if (workoutsValEl) {
      workoutsValEl.innerText = this.totalWorkouts || p.total_workouts || 0;
    }

    const streakValEl = document.getElementById('gauge-streak-val');
    if (streakValEl) {
      streakValEl.innerText = p.streak_days || 1;
    }

    // Hunter Bio Box
    const heightEl = document.getElementById('char-bio-height');
    if (heightEl) heightEl.innerText = `${p.height || 178} cm`;

    const weightEl = document.getElementById('char-bio-weight');
    if (weightEl) weightEl.innerText = `${Number(p.weight || 78).toFixed(1)} kg`;

    const ageEl = document.getElementById('char-bio-age');
    if (ageEl) ageEl.innerText = p.age || 25;

    const targetEl = document.getElementById('char-bio-target');
    if (targetEl) targetEl.innerText = `${Number(p.target_weight || 74).toFixed(1)} kg`;

    const hunterIdEl = document.getElementById('hunter-system-id');
    if (hunterIdEl) {
      const seed = Math.abs((p.name || 'ROM').split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 77000)) % 100000;
      hunterIdEl.innerText = p.hunter_id || `HNT-${String(seed).padStart(5, '0')}`;
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
      if (data.newly_unlocked_achievements && data.newly_unlocked_achievements.length > 0) {
        this.checkNewlyUnlocked(data.newly_unlocked_achievements);
      }
      await this.fetchTodayData();
    } catch (e) {
      console.error(e);
    }
  },

  async logSelectedFood() {
    if (!this.selectedFood) return;
    sfx.playClick();
    const unitEl = document.getElementById('portion-unit-select');
    const unit = unitEl ? unitEl.value : 'g';
    const amount = parseFloat(document.getElementById('portion-amount-input').value) || 1;
    let factor = 1;
    if (unit === 'g') factor = 1;
    else if (unit === 'tbsp') factor = 15;
    else if (unit === 'tsp') factor = 5;
    else if (unit === 'cup') factor = 240;
    else factor = this.selectedFood.serving_size_g || 100;

    const totalGrams = Math.max(1, Math.round(amount * factor));
    const baseServing = this.selectedFood.serving_size_g || 100;
    const ratio = totalGrams / baseServing;
    const mealType = document.getElementById('meal-type-select').value;

    const payload = {
      food_id: this.selectedFood.id,
      food_name: this.selectedFood.name_he || this.selectedFood.name,
      serving_count: ratio,
      serving_size_g: totalGrams,
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
      if (!res.ok) {
        throw new Error(data.error || 'שגיאת שרת ברישום הארוחה');
      }

      // Reset selection
      this.selectedFood = null;
      document.getElementById('staging-card').style.display = 'none';
      document.getElementById('food-search-input').value = '';

      if (data.skill_leveling && data.skill_leveling.leveled_up) {
        this.showSkillLevelUpModal(data.skill_leveling);
      } else if (data.leveling && data.leveling.leveled_up) {
        this.showLevelUpModal(data.leveling);
      } else {
        sfx.playSystemNotification();
      }

      if (data.newly_unlocked_achievements && data.newly_unlocked_achievements.length > 0) {
        this.checkNewlyUnlocked(data.newly_unlocked_achievements);
      }

      this.showToast(`[SYSTEM: ארוחה נרשמה בהצלחה! (+${data.exp_awarded || 25} EXP)]`);

      await this.fetchTodayData();
      await this.fetchSkills();
      await this.fetchDailyDebrief();
    } catch (e) {
      console.error('Error logging food:', e);
      alert('שגיאה ברישום הארוחה: ' + (e.message || e));
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

    // Close any modal on backdrop click
    document.querySelectorAll('.modal-overlay').forEach(modal => {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) {
          AppState.closeModal(modal.id);
        }
      });
    });

    // Close active modal on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(modal => {
          AppState.closeModal(modal.id);
        });
      }
    });
  },

  selectFood(item) {
    sfx.playClick();
    this.selectedFood = item;
    const staging = document.getElementById('staging-card');
    document.getElementById('staging-name').innerText = item.name_he || item.name;
    const amountInput = document.getElementById('portion-amount-input');
    const unitSelect = document.getElementById('portion-unit-select');
    if (amountInput) amountInput.value = 1;
    if (unitSelect) unitSelect.value = 'serving';
    this.updatePortionCalculations();
    staging.style.display = 'flex';
    staging.scrollIntoView({ behavior: 'smooth', block: 'center' });
  },

  onUnitChange() {
    const unit = document.getElementById('portion-unit-select').value;
    const amountInput = document.getElementById('portion-amount-input');
    if (unit === 'g') {
      amountInput.value = this.selectedFood ? (this.selectedFood.serving_size_g || 100) : 100;
      amountInput.step = 5;
    } else {
      amountInput.value = 1;
      amountInput.step = 0.5;
    }
    this.updatePortionCalculations();
  },

  updatePortionCalculations() {
    if (!this.selectedFood) return;
    const unitEl = document.getElementById('portion-unit-select');
    const amountEl = document.getElementById('portion-amount-input');
    const unit = unitEl ? unitEl.value : 'serving';
    const amount = parseFloat(amountEl ? amountEl.value : 1) || 1;
    let factor = 1;
    let unitLabel = 'גרם';

    if (unit === 'g') {
      factor = 1;
      unitLabel = 'גרם';
    } else if (unit === 'tbsp') {
      factor = 15;
      unitLabel = 'כפות';
    } else if (unit === 'tsp') {
      factor = 5;
      unitLabel = 'כפיות';
    } else if (unit === 'cup') {
      factor = 240;
      unitLabel = 'כוסות';
    } else if (unit === 'unit') {
      factor = this.selectedFood.serving_size_g || 100;
      unitLabel = 'יחידות';
    } else if (unit === 'serving') {
      factor = this.selectedFood.serving_size_g || 100;
      unitLabel = 'מנות';
    }

    const totalGrams = Math.max(1, Math.round(amount * factor));
    const baseServing = this.selectedFood.serving_size_g || 100;
    const multiplier = totalGrams / baseServing;

    const calcCal = Math.round(this.selectedFood.calories * multiplier);
    const calcP = Math.round(this.selectedFood.protein * multiplier * 10) / 10;
    const calcC = Math.round(this.selectedFood.carbs * multiplier * 10) / 10;
    const calcF = Math.round(this.selectedFood.fats * multiplier * 10) / 10;

    const previewEl = document.getElementById('staging-calc-preview');
    if (previewEl) {
      previewEl.innerHTML = `סה"כ: <strong>${totalGrams} גרם</strong> (${amount} ${unitLabel}) • <span style="color:#00f0ff;">${calcCal} קק"ל</span> | חלבון: <span style="color:#10b981;">${calcP}g</span> | פחמימה: ${calcC}g | שומן: ${calcF}g`;
    }
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
      if (data.newly_unlocked_achievements && data.newly_unlocked_achievements.length > 0) {
        this.checkNewlyUnlocked(data.newly_unlocked_achievements);
      }
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
      m.classList.add('active');
      m.style.display = 'flex';
      m.style.pointerEvents = 'auto';
      if (id === 'awakening-modal') {
        this.updateAwakeningPreview();
      }
    }
  },

  closeModal(id) {
    sfx.playClick();
    const m = document.getElementById(id);
    if (m) {
      m.classList.remove('active');
      m.style.display = 'none';
      m.style.pointerEvents = 'none';
    }
  },

  // Toast notifications
  showToast(message, type = 'info') {
    let container = document.getElementById('system-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'system-toast-container';
      container.style.cssText = 'position:fixed; bottom:76px; left:50%; transform:translateX(-50%); z-index:99999; display:flex; flex-direction:column; gap:8px; pointer-events:none; width:90%; max-width:380px; align-items:center;';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `system-toast ${type}`;
    toast.style.cssText = 'background:rgba(9,19,38,0.95); border:1.5px solid var(--hud-cyan); border-radius:10px; padding:10px 16px; color:#ffffff; font-size:12px; font-weight:800; box-shadow:0 0 20px rgba(0,240,255,0.4); text-align:center; backdrop-filter:blur(8px); transition:all 0.3s ease; opacity:0; transform:translateY(10px); pointer-events:auto;';
    toast.innerText = message;

    container.appendChild(toast);

    requestAnimationFrame(() => {
      toast.style.opacity = '1';
      toast.style.transform = 'translateY(0)';
    });

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(-10px)';
      setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 350);
    }, 3200);
  },

  // --- Auto-Snapshotting & Multi-Layer Persistence ---
  snapshotTimer: null,
  triggerDebouncedSnapshot() {
    if (this.snapshotTimer) clearTimeout(this.snapshotTimer);
    this.snapshotTimer = setTimeout(() => {
      this.saveLocalSnapshot();
    }, 1500);
  },

  async saveLocalSnapshot(optionalData = null) {
    try {
      if (optionalData) {
        localStorage.setItem('SOLO_HUNTER_SYSTEM_SNAPSHOT', JSON.stringify(optionalData));
        localStorage.setItem('SOLO_HUNTER_SNAPSHOT_TIMESTAMP', new Date().toISOString());
        this.updateBackupUI();
        return;
      }
      const res = await fetch('/api/backup');
      if (res.ok) {
        const data = await res.json();
        localStorage.setItem('SOLO_HUNTER_SYSTEM_SNAPSHOT', JSON.stringify(data));
        localStorage.setItem('SOLO_HUNTER_SNAPSHOT_TIMESTAMP', new Date().toISOString());
        this.updateBackupUI();
      }
    } catch (e) {
      console.warn('Auto-snapshot save failed:', e);
    }
  },

  updateBackupUI() {
    const timeEl = document.getElementById('backup-last-time-text');
    const badgeEl = document.getElementById('backup-sync-status-badge');
    const rawTime = localStorage.getItem('SOLO_HUNTER_SNAPSHOT_TIMESTAMP');
    if (timeEl && rawTime) {
      const d = new Date(rawTime);
      const timeFormatted = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const dateFormatted = d.toLocaleDateString('he-IL');
      timeEl.innerText = `סנכרון מקומי אחרון בדפדפן: ${dateFormatted} ב-${timeFormatted}`;
    }
    if (badgeEl) {
      badgeEl.innerText = '● סנכרון מקומי פעיל';
      badgeEl.style.color = '#34d399';
    }
  },

  checkDisasterRecovery() {
    try {
      const banner = document.getElementById('disaster-recovery-banner');
      if (!banner) return;
      const rawSnapshot = localStorage.getItem('SOLO_HUNTER_SYSTEM_SNAPSHOT');
      if (!rawSnapshot) {
        banner.style.display = 'none';
        return;
      }
      const snapshot = JSON.parse(rawSnapshot);
      const snapProfile = snapshot.hunter_profile || snapshot.profile || {};
      const snapDailyLogs = snapshot.daily_logs || snapshot.logs || [];
      const snapWorkouts = snapshot.workout_logs || [];
      const snapSupps = snapshot.supplements_log || [];

      const totalSnapRecords = snapDailyLogs.length + snapWorkouts.length + snapSupps.length;
      const isServerFresh = (!this.profile || this.profile.level <= 1) && (!this.todayMeals || this.todayMeals.length === 0);

      // If server is fresh but snapshot has higher level or existing history
      if (isServerFresh && (snapProfile.level > 1 || totalSnapRecords > 0)) {
        banner.style.display = 'block';
        const subEl = document.getElementById('disaster-banner-sub');
        if (subEl) {
          subEl.innerText = `נמצא גיבוי דפדפן ברמה ${snapProfile.level || 1} עם ${totalSnapRecords} רשומות היסטוריות. שחזר עכשיו כדי לא לאבד התקדמות.`;
        }
      } else {
        banner.style.display = 'none';
      }
    } catch (e) {
      console.warn('Disaster recovery check error:', e);
    }
  },

  async restoreFromLocalSnapshot() {
    sfx.playClick();
    try {
      const rawSnapshot = localStorage.getItem('SOLO_HUNTER_SYSTEM_SNAPSHOT');
      if (!rawSnapshot) {
        alert('לא נמצא גיבוי מקומי שמור בדפדפן.');
        return;
      }
      const snapshot = JSON.parse(rawSnapshot);
      const res = await fetch('/api/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(snapshot)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Restore failed');
      sfx.playLevelUp();
      const banner = document.getElementById('disaster-recovery-banner');
      if (banner) banner.style.display = 'none';
      this.showToast('✨ כל הנתונים שוחזרו בהצלחה מהגיבוי המקומי!');
      setTimeout(() => window.location.reload(), 600);
    } catch (err) {
      alert('שגיאה בשחזור מגיבוי מקומי: ' + err.message);
    }
  },

  // Export JSON Backup
  async exportBackup() {
    sfx.playClick();
    try {
      const res = await fetch('/api/backup');
      if (!res.ok) throw new Error('Backup failed');
      const data = await res.json();
      const nowStr = new Date().toISOString().slice(0, 10);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `solo_hunter_backup_${nowStr}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      this.showToast('✓ קובץ גיבוי מלא (JSON) הורד למכשירך בהצלחה!');
      this.saveLocalSnapshot(data);
    } catch (err) {
      console.error('Export backup failed, falling back:', err);
      window.location.href = '/api/backup';
    }
  },

  // Import JSON Backup
  async importBackupFile(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    sfx.playClick();
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      if (!parsed.hunter_profile && !parsed.profile) {
        throw new Error('קובץ לא תקין - מבנה נתוני צייד חסר');
      }
      if (!confirm(`האם לשחזר את כל נתוני המערכת מקובץ הגיבוי ${file.name}? פעולה זו תעדכן את השרת בכל הרמות, הסקילים והיומנים.`)) {
        event.target.value = '';
        return;
      }
      const res = await fetch('/api/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(parsed)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Restore failed');
      sfx.playLevelUp();
      this.saveLocalSnapshot(parsed);
      this.showToast('✨ כל הנתונים, הסקילים והיומנים שוחזרו בהצלחה!');
      setTimeout(() => window.location.reload(), 700);
    } catch (err) {
      alert('שגיאה בשחזור קובץ הגיבוי: ' + err.message);
    } finally {
      event.target.value = '';
    }
  },

  // --- Reset & Rebirth Controls ---
  openResetModal(mode = 'all') {
    sfx.playClick();
    this.openModal('reset-modal');
    const input = document.getElementById('rebirth-confirm-input');
    if (input) input.value = '';
  },

  async confirmResetToday() {
    if (!confirm('האם לאפס את נתוני היום הנוכחי בלבד?\n\nכל הארוחות, המים, התוספים ואימוני היום יימחקו.\nדרגת הצייד (Level), הסקילים וההיסטוריה הקודמת יישמרו במלואם.')) {
      return;
    }
    sfx.playClick();
    try {
      const res = await fetch('/api/reset/today', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Reset failed');
      sfx.playSystemNotification();
      this.showToast('🔄 נתוני יום זה אופסו בהצלחה!');
      this.closeModal('reset-modal');
      await this.fetchTodayData();
      await this.fetchSupplements();
      await this.fetchGarminStatus();
      await this.fetchDailyDebrief();
      this.saveLocalSnapshot();
    } catch (err) {
      alert('שגיאה באיפוס היום: ' + err.message);
    }
  },

  async confirmFullRebirth() {
    const input = document.getElementById('rebirth-confirm-input');
    const val = input ? input.value.trim().toLowerCase() : '';
    if (val !== 'אישור' && val !== 'rebirth') {
      alert('לאישור לידה מחדש, עליך להקליד "אישור" או "REBIRTH" בשדה המתאים.');
      if (input) input.focus();
      return;
    }

    sfx.playClick();

    // Step 1: Emergency Backup Download FIRST so data is guaranteed never lost!
    try {
      const resBackup = await fetch('/api/backup');
      if (resBackup.ok) {
        const backupData = await resBackup.json();
        const nowStr = new Date().toISOString().slice(0, 10);
        const blob = new Blob([JSON.stringify(backupData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `solo_hunter_emergency_backup_before_rebirth_${nowStr}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    } catch (e) {
      console.warn('Pre-rebirth emergency backup download failed:', e);
    }

    // Step 2: Call /api/reset/full
    try {
      const res = await fetch('/api/reset/full', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Rebirth failed');

      localStorage.removeItem('SOLO_HUNTER_SYSTEM_SNAPSHOT');
      localStorage.removeItem('hunter_profile');
      localStorage.removeItem('hunter_health_advisor');

      sfx.playLevelUp();
      alert('[SYSTEM: לידה מחדש הושלמה!]\nהצייד חזר לרמה 1 (E-Rank) וכל הסקילים אופסו לרמה 1.\nעותק גיבוי חירום הורד בהצלחה למכשירך.');
      window.location.reload();
    } catch (err) {
      alert('שגיאה בתהליך הלידה מחדש: ' + err.message);
    }
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
      statusEl.innerText = '[SYSTEM: מפעיל מנוע זיהוי ZXing וחיישני מצלמה...]';
      try {
        this.videoStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }
        });
        video.srcObject = this.videoStream;
        await video.play();
        statusEl.innerText = '[SYSTEM: סורק ZXing פעיל - כוון אל מרכז הברקוד...]';

        // 1. ZXing Continuous Video Stream Decoding
        if (window.ZXing && window.ZXing.BrowserMultiFormatReader) {
          try {
            if (!this.codeReader) {
              this.codeReader = new ZXing.BrowserMultiFormatReader();
            }
            this.codeReader.decodeFromVideoDevice(null, 'scanner-video', (result, err) => {
              if (result && result.getText()) {
                const detectedCode = result.getText();
                this.closeBarcodeScanner();
                this.lookupBarcode(detectedCode);
              }
            });
          } catch (zxErr) {
            console.warn('ZXing video decode initialization notice:', zxErr);
          }
        }

        // 2. BarcodeDetector fallback loop
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
                this.closeBarcodeScanner();
                this.lookupBarcode(detectedCode);
              }
            } catch (err) {}
          }, 250);
        }
      } catch (err) {
        console.warn('Live camera access error:', err);
        statusEl.innerText = '📱 לחץ על הכפתור הכחול למעלה לפתיחת מצלמת האייפון וצילום ישיר של הברקוד!';
      }
    } else {
      statusEl.innerText = '📱 לחץ על הכפתור הכחול למעלה לפתיחת מצלמת האייפון וצילום ישיר של הברקוד!';
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
    statusEl.innerText = '[SYSTEM: מנוע ZXing מעבד ומנתח את חתימת הברקוד...]';

    const reader = new FileReader();
    reader.onload = async (e) => {
      const img = new Image();
      img.onload = async () => {
        // 1. First Pass: Try ZXing Directly on the Source Image
        if (window.ZXing && window.ZXing.BrowserMultiFormatReader) {
          try {
            if (!this.codeReader) {
              this.codeReader = new ZXing.BrowserMultiFormatReader();
            }
            const zxResult = await this.codeReader.decodeFromImageElement(img);
            if (zxResult && zxResult.getText()) {
              const code = zxResult.getText();
              statusEl.innerText = `[✓ זוהה ברקוד: ${code}]`;
              sfx.playScanLock();
              this.lookupBarcode(code);
              return;
            }
          } catch (zxErr) {
            // Normal if first pass didn't catch angle
          }
        }

        // Draw to optimal canvas for multi-angle and contrast passes
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

        // 2. Second Pass: Native BarcodeDetector
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
            console.warn('BarcodeDetector notice:', err);
          }
        }

        // 3. Third Pass: Rotate 90 degrees with ZXing (Handles vertical/angled phone photos)
        if (window.ZXing && window.ZXing.BrowserMultiFormatReader) {
          try {
            const rotCanvas = document.createElement('canvas');
            rotCanvas.width = height;
            rotCanvas.height = width;
            const rotCtx = rotCanvas.getContext('2d');
            rotCtx.translate(height / 2, width / 2);
            rotCtx.rotate((90 * Math.PI) / 180);
            rotCtx.drawImage(canvas, -width / 2, -height / 2);

            const rotImg = new Image();
            rotImg.src = rotCanvas.toDataURL('image/jpeg', 0.95);
            await new Promise(r => rotImg.onload = r);

            const rotResult = await this.codeReader.decodeFromImageElement(rotImg);
            if (rotResult && rotResult.getText()) {
              const code = rotResult.getText();
              statusEl.innerText = `[✓ זוהה ברקוד בזווית 90°: ${code}]`;
              sfx.playScanLock();
              this.lookupBarcode(code);
              return;
            }
          } catch (rotErr) {}
        }

        // 4. Fourth Pass: Pure JS 1D Pattern Scanline
        const decoded = this.scan1DBarcodeFromCanvas(canvas);
        if (decoded) {
          statusEl.innerText = `[✓ זוהה ברקוד: ${decoded}]`;
          sfx.playScanLock();
          this.lookupBarcode(decoded);
          return;
        }

        // If not found by any engine
        statusEl.innerHTML = `
          <div style="color:#f87171; font-weight:700;">❌ לא זוהה ברקוד בבירור בתמונה</div>
          <div style="font-size:11px; color:#cbd5e1; margin-top:4px;">
            נסה לצלם שוב כשהברקוד קרוב ומואר, או הקלד את מספרי הברקוד למטה.
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
    if (this.codeReader) {
      try {
        this.codeReader.reset();
      } catch (e) {}
    }
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
    const normMeta = this.healthAdvisor.attent_normalization;
    const isNorm = normMeta && normMeta.is_active;

    // 0. Normalization Pill in Header & Badges
    const normPill = document.getElementById('attent-norm-pill');
    const hrBadge = document.getElementById('garmin-hr-badge');
    const stressBadge = document.getElementById('garmin-stress-badge');
    const bbBadge = document.getElementById('garmin-bb-badge');

    if (normPill) {
      if (isNorm) {
        normPill.style.display = 'flex';
        const pillText = document.getElementById('attent-norm-pill-text');
        if (pillText) pillText.innerText = normMeta.status_badge_he || '💊 פילטר אטנט פעיל (מנוקה מדעית)';
      } else {
        normPill.style.display = 'none';
      }
    }

    if (hrBadge) hrBadge.style.display = isNorm ? 'inline-block' : 'none';
    if (stressBadge) stressBadge.style.display = isNorm ? 'inline-block' : 'none';
    if (bbBadge) bbBadge.style.display = isNorm ? 'inline-block' : 'none';

    // 1. Heart Rate
    const hrEl = document.getElementById('garmin-hr-val');
    if (hrEl) hrEl.innerText = b.heart_rate || 68;
    const rhrEl = document.getElementById('garmin-resting-hr');
    if (rhrEl) {
      if (isNorm && b.raw_rhr) {
        rhrEl.innerHTML = `מנוחה מנורמלת: <strong>${b.resting_hr} bpm</strong> <span style="font-size:10px; color:#f87171; text-decoration:line-through;">(${b.raw_rhr} bpm)</span>`;
      } else {
        rhrEl.innerText = `מנוחה: ${b.resting_hr || 58} bpm`;
      }
    }

    // 2. Sleep Quality
    const sleepEl = document.getElementById('garmin-sleep-val');
    if (sleepEl) sleepEl.innerText = b.sleep_score || 82;
    const sleepHEl = document.getElementById('garmin-sleep-hours');
    if (sleepHEl) sleepHEl.innerText = `${b.sleep_hours || 7.2} שעות שינה`;

    // 3. Stress Level
    const stressEl = document.getElementById('garmin-stress-val');
    if (stressEl) stressEl.innerText = b.stress_level || 28;
    const stressStatEl = document.getElementById('garmin-stress-status');
    if (stressStatEl) {
      if (isNorm && b.raw_stress !== undefined) {
        stressStatEl.innerHTML = `${b.stress_state_he || 'מנוחה'} <span style="font-size:10px; color:#f87171; text-decoration:line-through;">(שעון: ${b.raw_stress})</span>`;
      } else {
        const s = b.stress_level || 28;
        stressStatEl.innerText = s < 25 ? 'מנוחה (נמוך)' : (s < 50 ? 'נמוך-בינוני' : (s < 75 ? 'בינוני' : 'גבוה'));
      }
    }

    // 4. Body Battery
    const bbEl = document.getElementById('garmin-battery-val');
    if (bbEl) bbEl.innerText = `${b.body_battery || 75}%`;
    const bbStatEl = document.getElementById('garmin-battery-status');
    if (bbStatEl) {
      if (isNorm && b.raw_bb !== undefined) {
        bbStatEl.innerHTML = `מוגן משחיקת אטנט <span style="font-size:10px; color:#f87171; text-decoration:line-through;">(${b.raw_bb}%)</span>`;
      } else {
        const bb = b.body_battery || 75;
        bbStatEl.innerText = bb > 70 ? 'אנרגיה טעונה' : (bb > 40 ? 'רמה בינונית' : 'מאגר נמוך');
      }
    }

    const stepsEl = document.getElementById('garmin-steps-val');
    if (stepsEl) stepsEl.innerText = (b.steps || 8500).toLocaleString();
    const activeEl = document.getElementById('garmin-active-cals-val');
    if (activeEl) activeEl.innerText = `+${b.active_calories || 450}`;
    const spo2El = document.getElementById('garmin-spo2-val');
    if (spo2El) spo2El.innerText = `${b.spo2_pct || 98}%`;

    // 5. Update Real-Time Status Strip
    const timeEl = document.getElementById('garmin-sync-time-badge');
    if (timeEl) {
      timeEl.innerText = b.sync_timestamp ? `סונכרן: היום ב-${b.sync_timestamp}` : 'סונכרן היום';
    }
    const sourceEl = document.getElementById('garmin-source-badge');
    if (sourceEl) {
      const srcMap = {
        'connect_iq': 'CONNECT IQ',
        'connect_iq_venu4': 'CONNECT IQ',
        'ios_shortcuts': 'SHORTCUTS',
        'ios_shortcuts_test': 'SHORTCUTS',
        'csv_file': 'CSV FILE',
        'fit_file': 'FIT FILE',
        'webhook': 'WEBHOOK',
        'smart_diurnal': 'SMART AUTO',
        'manual': 'MANUAL'
      };
      const rawSrc = (b.sync_source || 'connect_iq').toLowerCase();
      sourceEl.innerText = srcMap[rawSrc] || rawSrc.toUpperCase();
    }
    const statusTextEl = document.getElementById('garmin-status-text');
    if (statusTextEl) {
      statusTextEl.innerText = 'Garmin Venu 4: מקושר ומסונכרן';
    }
    const statusInd = document.getElementById('garmin-status-indicator');
    if (statusInd) {
      statusInd.className = 'garmin-status-indicator online';
    }
  },

  openAttentNormModal() {
    sfx.playClick();
    const b = this.healthAdvisor?.biometrics;
    const meta = this.healthAdvisor?.attent_normalization;
    if (meta && meta.is_active && b) {
      const sub = document.getElementById('norm-modal-subtitle');
      if (sub) sub.innerText = `נטילה לפני ${meta.elapsed_hours.toFixed(1)} שעות • מינון ${meta.dose_mg}mg (עוצמה פרמקולוגית ${meta.potency_pct}%)`;

      const stressReal = document.getElementById('norm-comp-stress-real');
      const stressRaw = document.getElementById('norm-comp-stress-raw');
      const stressDesc = document.getElementById('norm-comp-stress-desc');
      if (stressReal) stressReal.innerText = b.stress_level;
      if (stressRaw) stressRaw.innerText = `${b.raw_stress} (שעון)`;
      if (stressDesc) stressDesc.innerText = `הטיה של ${meta.stress_offset}+ נקודות נוטרלה מדעית`;

      const rhrReal = document.getElementById('norm-comp-rhr-real');
      const rhrRaw = document.getElementById('norm-comp-rhr-raw');
      const rhrDesc = document.getElementById('norm-comp-rhr-desc');
      if (rhrReal) rhrReal.innerText = `${b.resting_hr} bpm`;
      if (rhrRaw) rhrRaw.innerText = `${b.raw_rhr} bpm`;
      if (rhrDesc) rhrDesc.innerText = `הטיה כרונוטרופית של ${meta.rhr_offset}+ bpm נוטרלה`;
    }
    this.openModal('attent-norm-modal');
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
            <div style="display:flex; gap:6px; align-items:center;">
              <button type="button" class="attent-cancel-btn" onclick="AppState.openAttentModal()" style="border-color:#c084fc; color:#f3e8ff; background:rgba(168,85,247,0.25);" title="ערוך מינון או שעת נטילה">✏️ ערוך</button>
              <button type="button" class="attent-cancel-btn" onclick="AppState.cancelAttent()" title="בטל רישום">✕ ביטול</button>
            </div>
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
              <span style="font-size:10px; color:var(--text-secondary); display:block;">נטלת אטנט היום? לחץ כאן לבחירת מינון (10, 15, 20, 30mg) ושעת נטילה</span>
            </div>
          </div>
          <button type="button" class="badge-button" onclick="event.stopPropagation(); AppState.openAttentModal();" style="background:rgba(168,85,247,0.25); border:1px solid #c084fc; color:#f3e8ff; font-size:11px; padding:6px 12px; border-radius:6px; cursor:pointer;">
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

  openGarminModal(tab = 'quick') {
    sfx.playClick();
    if (this.healthAdvisor && this.healthAdvisor.biometrics) {
      const b = this.healthAdvisor.biometrics;
      const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.value = val;
      };
      setVal('garmin-input-hr', b.heart_rate || 68);
      setVal('garmin-input-rhr', b.resting_hr || 58);
      setVal('garmin-input-sleep-score', b.sleep_score || 82);
      setVal('garmin-input-sleep-hours', b.sleep_hours || 7.2);
      setVal('garmin-input-stress', b.stress_level || 28);
      setVal('garmin-input-bb', b.body_battery || 75);
      setVal('garmin-input-steps', b.steps || 8500);
      setVal('garmin-input-active-cals', b.active_calories || 450);
    }
    this.switchGarminTab(tab);
    this.setupGarminDropzone();
    this.fetchGarminWebhookInfo();
    document.getElementById('garmin-modal').classList.add('active');
  },

  switchGarminTab(tab) {
    ['quick', 'file', 'webhook'].forEach(t => {
      const btn = document.getElementById(`btn-tab-garmin-${t}`);
      const pane = document.getElementById(`garmin-pane-${t}`);
      if (btn) btn.classList.toggle('active', t === tab);
      if (pane) {
        pane.style.display = (t === tab) ? 'block' : 'none';
        if (t === tab) pane.classList.add('active');
        else pane.classList.remove('active');
      }
    });
  },

  async fetchGarminWebhookInfo() {
    try {
      const res = await fetch('/api/garmin/webhook-info');
      const data = await res.json();
      const input = document.getElementById('garmin-webhook-url-display');
      if (input && data.webhook_url) {
        input.value = data.webhook_url;
      }
    } catch (e) {
      const input = document.getElementById('garmin-webhook-url-display');
      if (input) input.value = `${window.location.origin}/api/garmin/webhook`;
    }
  },

  copyWebhookUrl() {
    const input = document.getElementById('garmin-webhook-url-display');
    if (input && input.value) {
      navigator.clipboard.writeText(input.value).then(() => {
        const btn = document.querySelector('.copy-url-btn');
        if (btn) {
          const prev = btn.innerText;
          btn.innerText = '✓ הועתק!';
          setTimeout(() => btn.innerText = prev, 2000);
        }
        sfx.playSystemNotification();
      }).catch(() => {
        input.select();
        document.execCommand('copy');
      });
    }
  },

  async testGarminWebhook() {
    sfx.playClick();
    const testPayload = {
      steps: 9450,
      active_calories: 520,
      heart_rate: 68,
      resting_hr: 56,
      sleep_score: 85,
      sleep_hours: 7.6,
      stress_level: 24,
      body_battery: 80,
      source: "ios_shortcuts_test"
    };
    try {
      const res = await fetch('/api/garmin/webhook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(testPayload)
      });
      const data = await res.json();
      if (data.data) {
        this.healthAdvisor = data.data;
        this.renderAll();
        sfx.playLevelUp();
        alert('✓ דגימת Webhook התקבלה בהצלחה בשרת! המדדים ב-HUD עודכנו.');
        this.closeModal('garmin-modal');
      }
    } catch (e) {
      alert('שגיאה בבדיקת Webhook: ' + e.message);
    }
  },

  setupGarminDropzone() {
    const dropzone = document.getElementById('garmin-dropzone');
    if (!dropzone || dropzone.dataset.initialized) return;
    dropzone.dataset.initialized = 'true';

    ['dragenter', 'dragover'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('dragover');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      const files = dt.files;
      if (files && files.length > 0) {
        this.processGarminFile(files[0]);
      }
    });
  },

  handleGarminFileSelected(event) {
    const files = event.target.files;
    if (files && files.length > 0) {
      this.processGarminFile(files[0]);
    }
  },

  async processGarminFile(file) {
    sfx.playClick();
    const statusEl = document.getElementById('garmin-file-status');
    if (statusEl) {
      statusEl.style.display = 'block';
      statusEl.innerText = `⏳ מפענח קובץ ${file.name}...`;
    }

    const reader = new FileReader();
    const isFit = file.name.toLowerCase().endsWith('.fit');

    reader.onload = async (e) => {
      try {
        let payload = { filename: file.name };
        if (isFit) {
          const base64Data = e.target.result.split(',')[1] || e.target.result;
          payload.base64 = base64Data;
        } else {
          payload.content = e.target.result;
        }

        const res = await fetch('/api/garmin/upload-file', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.data) {
          this.healthAdvisor = data.data;
          this.renderAll();
          sfx.playLevelUp();
          if (statusEl) {
            statusEl.innerText = `✓ קובץ ${file.name} סונכרן בהצלחה! צעדים: ${data.data.biometrics.steps?.toLocaleString() || '--'}`;
          }
          setTimeout(() => {
            this.closeModal('garmin-modal');
          }, 1500);
        } else {
          alert(data.error || 'שגיאה בפיענוח קובץ');
        }
      } catch (err) {
        alert('שגיאה בהעלאת קובץ: ' + err.message);
      }
    };

    if (isFit) {
      reader.readAsDataURL(file);
    } else {
      reader.readAsText(file);
    }
  },

  async triggerSmartGarminSync() {
    sfx.playClick();
    try {
      const res = await fetch('/api/garmin/smart-sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      const data = await res.json();
      if (data.data) {
        this.healthAdvisor = data.data;
        this.renderAll();
        sfx.playSystemNotification();
        this.closeModal('garmin-modal');

        const hud = document.getElementById('garmin-hud-card');
        if (hud) {
          hud.style.boxShadow = '0 0 35px rgba(0, 240, 255, 0.6)';
          setTimeout(() => {
            hud.style.boxShadow = '0 0 20px rgba(0, 240, 255, 0.15)';
          }, 1200);
        }
      }
    } catch (e) {
      alert('שגיאה בסנכרון חכם: ' + e.message);
    }
  },

  setGarminPreset(preset) {
    sfx.playClick();
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val;
    };

    if (preset === 'rest') {
      setVal('garmin-input-hr', 60);
      setVal('garmin-input-rhr', 52);
      setVal('garmin-input-sleep-score', 90);
      setVal('garmin-input-sleep-hours', 8.2);
      setVal('garmin-input-stress', 16);
      setVal('garmin-input-bb', 92);
      setVal('garmin-input-steps', 4500);
      setVal('garmin-input-active-cals', 160);
    } else if (preset === 'normal') {
      setVal('garmin-input-hr', 68);
      setVal('garmin-input-rhr', 56);
      setVal('garmin-input-sleep-score', 84);
      setVal('garmin-input-sleep-hours', 7.4);
      setVal('garmin-input-stress', 28);
      setVal('garmin-input-bb', 75);
      setVal('garmin-input-steps', 8500);
      setVal('garmin-input-active-cals', 450);
    } else if (preset === 'workout') {
      setVal('garmin-input-hr', 78);
      setVal('garmin-input-rhr', 58);
      setVal('garmin-input-sleep-score', 84);
      setVal('garmin-input-sleep-hours', 7.5);
      setVal('garmin-input-stress', 48);
      setVal('garmin-input-bb', 65);
      setVal('garmin-input-steps', 13800);
      setVal('garmin-input-active-cals', 720);
    } else if (preset === 'deficit') {
      setVal('garmin-input-hr', 78);
      setVal('garmin-input-rhr', 64);
      setVal('garmin-input-sleep-score', 54);
      setVal('garmin-input-sleep-hours', 5.0);
      setVal('garmin-input-stress', 64);
      setVal('garmin-input-bb', 35);
      setVal('garmin-input-steps', 7200);
      setVal('garmin-input-active-cals', 320);
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
      active_calories: parseInt(document.getElementById('garmin-input-active-cals').value) || 450,
      source: "manual"
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

  openAttentModal(targetDate = null) {
    sfx.playClick();
    const activeAttent = this.healthAdvisor?.attent;
    const timeInput = document.getElementById('attent-input-time');
    const dateInput = document.getElementById('attent-input-date');
    const submitBtn = document.getElementById('attent-submit-btn');

    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const todayStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;

    if (dateInput) {
      dateInput.value = targetDate || todayStr;
    }

    if (timeInput) {
      timeInput.value = (activeAttent && activeAttent.timestamp) ? activeAttent.timestamp : `${hh}:${mm}`;
    }

    const currentDose = (activeAttent && activeAttent.dose_mg) ? activeAttent.dose_mg : (this.selectedAttentDose || 20);
    this.selectAttentDose(currentDose);

    if (submitBtn) {
      submitBtn.innerText = (activeAttent && activeAttent.is_active) ? '💾 שמור עדכון מנת אטנט' : '✨ הפעל BUFF שיקוי ריכוז (רשום נטילה)';
    }

    const cancelWrap = document.getElementById('attent-active-cancel-wrap');
    if (cancelWrap) {
      const isActive = this.healthAdvisor?.attent?.is_active;
      cancelWrap.style.display = isActive ? 'block' : 'none';
    }

    this.openModal('attent-modal');
  },

  setAttentTime(timeStr) {
    sfx.playClick();
    const timeInput = document.getElementById('attent-input-time');
    if (timeInput) timeInput.value = timeStr;
    document.querySelectorAll('.time-presets-row .preset-pill').forEach(btn => {
      btn.classList.remove('active');
    });
    const idMap = { '07:30': 'attent-time-0730', '09:00': 'attent-time-0900', '11:00': 'attent-time-1100', '13:30': 'attent-time-1330', '20:00': 'attent-time-2000' };
    if (idMap[timeStr]) {
      const btn = document.getElementById(idMap[timeStr]);
      if (btn) btn.classList.add('active');
    }
  },

  setAttentTimeNow() {
    sfx.playClick();
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const timeInput = document.getElementById('attent-input-time');
    if (timeInput) timeInput.value = `${hh}:${mm}`;
    document.querySelectorAll('.time-presets-row .preset-pill').forEach(btn => {
      btn.classList.remove('active');
    });
    const nowBtn = document.getElementById('attent-time-now');
    if (nowBtn) nowBtn.classList.add('active');
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
    const timeVal = document.getElementById('attent-input-time')?.value || '09:00';
    const duration = parseFloat(document.getElementById('attent-input-duration')?.value) || 7.0;
    const notes = document.getElementById('attent-input-notes')?.value || 'שיקוי ריכוז והיפר-פוקוס';
    const dateVal = document.getElementById('attent-input-date')?.value || '';

    try {
      const res = await fetch('/api/medication/attent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dose_mg: dose,
          timestamp: timeVal,
          duration_hours: duration,
          notes: notes,
          date: dateVal
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'שגיאת שרת ברישום אטנט');
      }
      if (data.data) {
        this.healthAdvisor = data.data;
        this.renderAll();
        sfx.playPotion();
        this.closeModal('attent-modal');
        this.showToast(`[SYSTEM: שיקוי ריכוז (${dose}mg) נרשם בהצלחה ב-${timeVal}!]`);
        await this.fetchDailyDebrief();
        await this.fetchLongTermInsights(this.longTermWindow || 14);
        if (this.calendarDaysData) {
          await this.fetchCalendarData(this.calendarCurrentMonth);
        }
      }
    } catch (e) {
      console.error('Error in saveAttentLog:', e);
      alert('שגיאה ברישום נטילת אטנט: ' + (e.message || e));
    }
  },

  async cancelAttent() {
    sfx.playClick();
    if (!confirm('האם לבטל את רישום מנת האטנט של היום?')) return;
    try {
      const res = await fetch('/api/medication/attent', { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'שגיאת שרת בביטול אטנט');
      }
      if (data.data) {
        this.healthAdvisor = data.data;
        this.renderAll();
        sfx.playSystemNotification();
        this.closeModal('attent-modal');
        this.showToast('✕ רישום אטנט פעיל בוטל');
        await this.fetchDailyDebrief();
        await this.fetchLongTermInsights(this.longTermWindow || 14);
        if (this.calendarDaysData) {
          await this.fetchCalendarData(this.calendarCurrentMonth);
        }
      }
    } catch (e) {
      console.error('Error in cancelAttent:', e);
      alert('שגיאה בביטול רישום אטנט: ' + (e.message || e));
    }
  },

  // ==========================================
  // ACTIVITY CALENDAR & CHRONIC PROGRESSION
  // ==========================================
  calendarCurrentMonth: '',
  calendarSelectedDay: '',
  calendarDaysData: null,

  openCalendarModal(targetMonth = null) {
    sfx.playClick();
    if (!this.calendarCurrentMonth || targetMonth) {
      const now = new Date();
      this.calendarCurrentMonth = targetMonth || `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
    }
    this.openModal('calendar-modal');
    this.fetchCalendarData(this.calendarCurrentMonth);
  },

  async changeCalendarMonth(delta) {
    sfx.playClick();
    const parts = this.calendarCurrentMonth.split('-').map(Number);
    let year = parts[0];
    let month = parts[1] + delta;
    if (month < 1) {
      month = 12;
      year -= 1;
    } else if (month > 12) {
      month = 1;
      year += 1;
    }
    this.calendarCurrentMonth = `${year}-${String(month).padStart(2,'0')}`;
    await this.fetchCalendarData(this.calendarCurrentMonth);
  },

  async resetCalendarToToday() {
    sfx.playClick();
    const now = new Date();
    this.calendarCurrentMonth = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
    await this.fetchCalendarData(this.calendarCurrentMonth);
    const todayStr = `${this.calendarCurrentMonth}-${String(now.getDate()).padStart(2,'0')}`;
    this.selectCalendarDay(todayStr);
  },

  async fetchCalendarData(monthStr) {
    try {
      const res = await fetch(`/api/history/calendar?month=${monthStr}`);
      const data = await res.json();
      this.calendarDaysData = data.days || {};
      this.renderCalendar();
      const now = new Date();
      const todayStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
      const defaultSelect = this.calendarDaysData[todayStr] ? todayStr : Object.keys(this.calendarDaysData)[0];
      if (defaultSelect && !this.calendarSelectedDay) {
        this.selectCalendarDay(defaultSelect);
      } else if (this.calendarSelectedDay && this.calendarDaysData[this.calendarSelectedDay]) {
        this.selectCalendarDay(this.calendarSelectedDay);
      }
    } catch (e) {
      console.error('Error fetching calendar data:', e);
    }
  },

  renderCalendar() {
    const grid = document.getElementById('calendar-days-grid');
    const titleEl = document.getElementById('calendar-month-title');
    if (!grid || !this.calendarCurrentMonth) return;

    const parts = this.calendarCurrentMonth.split('-').map(Number);
    const year = parts[0];
    const month = parts[1];

    const monthNames = ['', 'ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני', 'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר'];
    if (titleEl) {
      titleEl.innerText = `${monthNames[month]} ${year}`;
    }

    const firstDayIndex = new Date(year, month - 1, 1).getDay(); // 0 is Sunday
    const daysInMonth = new Date(year, month, 0).getDate();

    const now = new Date();
    const todayStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;

    let html = '';

    // Empty leading offset cells
    for (let i = 0; i < firstDayIndex; i++) {
      html += `<div class="cal-day-cell empty-cell"></div>`;
    }

    // Days in month
    for (let day = 1; day <= daysInMonth; day++) {
      const dateKey = `${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
      const dayData = this.calendarDaysData ? this.calendarDaysData[dateKey] : null;
      const isToday = (dateKey === todayStr);
      const isSelected = (dateKey === this.calendarSelectedDay);

      let badgesHtml = '';
      let scoreDotHtml = '';

      if (dayData && dayData.has_data) {
        if (dayData.daily_score >= 80) {
          scoreDotHtml = `<span class="cal-day-score-dot" style="background:#10b981;" title="ציון יום: ${dayData.daily_score}"></span>`;
        } else if (dayData.daily_score >= 50) {
          scoreDotHtml = `<span class="cal-day-score-dot" style="background:#f59e0b;" title="ציון יום: ${dayData.daily_score}"></span>`;
        }

        if (dayData.has_attent) {
          badgesHtml += `<span class="cal-mini-icon" title="אטנט ${dayData.attent?.dose_mg || 20}mg">💊</span>`;
        }
        if (dayData.nutrition && dayData.nutrition.logged) {
          const hitTarget = dayData.nutrition.protein >= (dayData.nutrition.target_protein * 0.9);
          badgesHtml += `<span class="cal-mini-icon" title="חלבון: ${dayData.nutrition.protein}g">${hitTarget ? '🎯' : '🍏'}</span>`;
        }
        if (dayData.workout_count > 0) {
          badgesHtml += `<span class="cal-mini-icon" title="${dayData.workout_count} אימונים">⚔️</span>`;
        }
        if (dayData.garmin && dayData.garmin.sleep_hours) {
          badgesHtml += `<span class="cal-mini-icon" title="שינה: ${dayData.garmin.sleep_hours}h">💤</span>`;
        }
      }

      html += `
        <div class="cal-day-cell ${isToday ? 'is-today' : ''} ${isSelected ? 'is-selected' : ''}" onclick="AppState.selectCalendarDay('${dateKey}')">
          <div class="cal-day-top">
            <span class="cal-day-num">${day}</span>
            ${scoreDotHtml}
          </div>
          <div class="cal-badges-mini">
            ${badgesHtml}
          </div>
        </div>
      `;
    }

    grid.innerHTML = html;
  },

  async selectCalendarDay(dateStr) {
    sfx.playClick();
    this.calendarSelectedDay = dateStr;
    this.renderCalendar();

    const dateHeader = document.getElementById('cal-detail-date');
    const badgeHeader = document.getElementById('cal-detail-badge');
    const contentEl = document.getElementById('cal-detail-content');

    if (dateHeader) dateHeader.innerText = `פירוט יום: ${dateStr}`;

    try {
      const res = await fetch(`/api/history/calendar/day?date=${dateStr}`);
      const data = await res.json();

      const daySummary = this.calendarDaysData ? this.calendarDaysData[dateStr] : null;
      if (badgeHeader) {
        badgeHeader.innerText = daySummary ? `ציון יום: ${daySummary.daily_score || 0}/100` : '--';
      }

      if (!contentEl) return;

      const hasActivity = (data.meals && data.meals.length > 0) || (data.total_water_ml > 0) || (data.garmin) || (data.medications && data.medications.length > 0) || (data.workouts && data.workouts.length > 0) || (data.supplements && data.supplements.length > 0);

      if (!hasActivity) {
        contentEl.innerHTML = `
          <div style="padding:12px; text-align:center; color:var(--text-secondary); font-size:12px;">
            <div>אין פעילות רשומה ביום זה.</div>
            <div style="margin-top:8px; display:flex; gap:8px; justify-content:center;">
              <button type="button" class="preset-pill" onclick="AppState.openAttentModal('${dateStr}')">+ רשום אטנט</button>
            </div>
          </div>
        `;
        return;
      }

      const totalCals = data.meals ? Math.round(data.meals.reduce((s, m) => s + (m.calories || 0), 0)) : 0;
      const totalP = data.meals ? Math.round(data.meals.reduce((s, m) => s + (m.protein || 0), 0)) : 0;
      const targetCals = data.profile?.target_calories || 2200;
      const targetP = data.profile?.target_protein || 160;

      const attentLog = (data.medications || []).find(m => m.med_name.toLowerCase() === 'attent');

      contentEl.innerHTML = `
        <div class="cal-detail-grid">
          <div class="cal-detail-box">
            <div class="cal-detail-box-title"><span>💊</span> אטנט / Attent</div>
            <div class="cal-detail-box-val" style="color:#c084fc;">
              ${attentLog ? `${attentLog.dose_mg}mg` : 'יום חופש (Drug Holiday)'}
            </div>
            <div class="cal-detail-box-sub">
              ${attentLog ? `נלקח ב-${attentLog.timestamp}` : 'רגישות קולטנים נשמרת'}
            </div>
          </div>

          <div class="cal-detail-box">
            <div class="cal-detail-box-title"><span>🥩</span> חלבון וקלוריות</div>
            <div class="cal-detail-box-val">
              ${totalP}g / ${totalCals} kcal
            </div>
            <div class="cal-detail-box-sub">
              יעד: ${targetP}g חלבון • ${targetCals} קק"ל
            </div>
          </div>

          <div class="cal-detail-box">
            <div class="cal-detail-box-title"><span>💧</span> מאזן מים</div>
            <div class="cal-detail-box-val" style="color:#38bdf8;">
              ${data.total_water_ml || 0} ml
            </div>
            <div class="cal-detail-box-sub">
              יעד: ${data.profile?.target_water || 3000} ml
            </div>
          </div>

          <div class="cal-detail-box">
            <div class="cal-detail-box-title"><span>⌚</span> Garmin Venu 4</div>
            <div class="cal-detail-box-val" style="color:#34d399;">
              ${data.garmin ? `${data.garmin.sleep_hours || 0}h שינה • ${data.garmin.steps || 0} צעדים` : 'ללא סנכרון'}
            </div>
            <div class="cal-detail-box-sub">
              ${data.garmin ? `דופק מנוחה: ${data.garmin.resting_hr || '--'} bpm • סטרס: ${data.garmin.stress_level || '--'}` : '--'}
            </div>
          </div>
        </div>

        ${data.workouts && data.workouts.length > 0 ? `
          <div style="margin-top:10px; padding-top:8px; border-top:1px solid rgba(255,255,255,0.06);">
            <div style="font-size:11px; font-weight:800; color:#e2e8f0; margin-bottom:4px;">⚔️ אימונים שבוצעו (${data.workouts.length}):</div>
            <div style="display:flex; flex-direction:column; gap:4px;">
              ${data.workouts.map(w => `
                <div style="font-size:11px; color:var(--text-secondary); background:rgba(0,0,0,0.2); padding:4px 8px; border-radius:4px;">
                  <strong style="color:#f1f5f9;">${w.title}</strong> • ${w.duration_min} דק׳ • ${w.calories_burned} קק"ל
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}

        ${data.meals && data.meals.length > 0 ? `
          <div style="margin-top:10px; padding-top:8px; border-top:1px solid rgba(255,255,255,0.06);">
            <div style="font-size:11px; font-weight:800; color:#e2e8f0; margin-bottom:4px;">🍽️ ארוחות שנרשמו (${data.meals.length}):</div>
            <div style="display:flex; flex-wrap:wrap; gap:4px;">
              ${data.meals.map(m => `
                <span style="font-size:10px; color:#cbd5e1; background:rgba(255,255,255,0.05); padding:2px 6px; border-radius:4px;">
                  ${m.food_name} (${Math.round(m.calories)} kcal)
                </span>
              `).join('')}
            </div>
          </div>
        ` : ''}
      `;
    } catch (e) {
      console.error('Error loading day detail:', e);
    }
  },

  // ==========================================
  // LONG-TERM EVIDENCE-BASED RESEARCH ENGINE
  // ==========================================
  longTermWindow: 14,
  longTermData: null,

  async switchLongTermWindow(days) {
    sfx.playClick();
    this.longTermWindow = days;
    [7, 14, 30].forEach(d => {
      const btn = document.getElementById(`lt-btn-${d}`);
      if (btn) {
        if (d === days) btn.classList.add('active');
        else btn.classList.remove('active');
      }
    });
    await this.fetchLongTermInsights(days);
  },

  async fetchLongTermInsights(window = 14) {
    try {
      const res = await fetch(`/api/history/long-term-insights?window=${window}`);
      const data = await res.json();
      this.longTermData = data;
      this.renderLongTermInsights(data);
    } catch (e) {
      console.error('Error fetching long-term insights:', e);
    }
  },

  renderLongTermInsights(data) {
    if (!data) return;
    const scoreVal = document.getElementById('lt-score-val');
    const headlineEl = document.getElementById('lt-status-headline');
    const summaryEl = document.getElementById('lt-status-summary');
    const gridEl = document.getElementById('lt-pillars-grid');

    if (scoreVal) scoreVal.innerText = data.composite_score;
    if (headlineEl) headlineEl.innerText = data.headline;
    if (summaryEl) summaryEl.innerText = data.summary;

    if (!gridEl || !data.pillars) return;

    const p = data.pillars;

    gridEl.innerHTML = `
      <!-- Pillar 1: Dopamine & Attent Tolerance -->
      <div class="lt-pillar-card">
        <div class="lt-pillar-top">
          <div class="lt-pillar-title-wrap">
            <span class="lt-pillar-icon">💊</span>
            <span class="lt-pillar-title">${p.dopamine.title}</span>
          </div>
          <span class="lt-pillar-badge ${p.dopamine.badge_type}">${p.dopamine.badge}</span>
        </div>
        <div class="lt-pillar-stats-row">
          <span class="lt-stat-chip">נטילה: <strong>${p.dopamine.days_taken} ימים</strong></span>
          <span class="lt-stat-chip">חופש: <strong>${p.dopamine.drug_holidays} ימים</strong></span>
          <span class="lt-stat-chip">מנה ממוצעת: <strong>${p.dopamine.avg_dose_mg}mg</strong></span>
        </div>
        <div class="lt-pillar-insight">${p.dopamine.insight}</div>
        <div class="lt-pillar-evidence-box">🔬 מחקר: ${p.dopamine.citation}</div>
        <div class="lt-pillar-action-box">👉 ${p.dopamine.action}</div>
      </div>

      <!-- Pillar 2: Muscle Protein Synthesis -->
      <div class="lt-pillar-card">
        <div class="lt-pillar-top">
          <div class="lt-pillar-title-wrap">
            <span class="lt-pillar-icon">🥩</span>
            <span class="lt-pillar-title">${p.protein.title}</span>
          </div>
          <span class="lt-pillar-badge ${p.protein.badge_type}">${p.protein.badge}</span>
        </div>
        <div class="lt-pillar-stats-row">
          <span class="lt-stat-chip">ממוצע: <strong>${p.protein.avg_daily_protein}g/יום</strong></span>
          <span class="lt-stat-chip">יחס משקל: <strong>${p.protein.protein_per_kg} g/kg</strong></span>
          <span class="lt-stat-chip">עמידה ביעד: <strong>${p.protein.days_hit_target}/${p.protein.total_logged_days} ימים</strong></span>
        </div>
        <div class="lt-pillar-insight">${p.protein.insight}</div>
        <div class="lt-pillar-evidence-box">🔬 מחקר: ${p.protein.citation}</div>
        <div class="lt-pillar-action-box">👉 ${p.protein.action}</div>
      </div>

      <!-- Pillar 3: Autonomic Nervous System & HRV Allostasis -->
      <div class="lt-pillar-card">
        <div class="lt-pillar-top">
          <div class="lt-pillar-title-wrap">
            <span class="lt-pillar-icon">🫀</span>
            <span class="lt-pillar-title">${p.autonomic.title}</span>
          </div>
          <span class="lt-pillar-badge ${p.autonomic.badge_type}">${p.autonomic.status}</span>
        </div>
        <div class="lt-pillar-stats-row">
          <span class="lt-stat-chip">דופק אטנט: <strong>${p.autonomic.avg_rhr_attent ? p.autonomic.avg_rhr_attent + ' bpm' : '--'}</strong></span>
          <span class="lt-stat-chip">דופק חופש: <strong>${p.autonomic.avg_rhr_off ? p.autonomic.avg_rhr_off + ' bpm' : '--'}</strong></span>
          <span class="lt-stat-chip">הפרש: <strong>${p.autonomic.rhr_delta_bpm > 0 ? '+' : ''}${p.autonomic.rhr_delta_bpm} bpm</strong></span>
        </div>
        <div class="lt-pillar-insight">${p.autonomic.insight}</div>
        <div class="lt-pillar-evidence-box">🔬 מחקר: ${p.autonomic.citation}</div>
        <div class="lt-pillar-action-box">👉 ${p.autonomic.action}</div>
      </div>

      <!-- Pillar 4: Chronic Sleep Debt -->
      <div class="lt-pillar-card">
        <div class="lt-pillar-top">
          <div class="lt-pillar-title-wrap">
            <span class="lt-pillar-icon">💤</span>
            <span class="lt-pillar-title">${p.sleep.title}</span>
          </div>
          <span class="lt-pillar-badge ${p.sleep.badge_type}">${p.sleep.badge}</span>
        </div>
        <div class="lt-pillar-stats-row">
          <span class="lt-stat-chip">ממוצע שינה: <strong>${p.sleep.avg_hours} שעות</strong></span>
          <span class="lt-stat-chip">ציון Garmin: <strong>${p.sleep.avg_score}/100</strong></span>
          <span class="lt-stat-chip">חוב שינה: <strong>${p.sleep.sleep_debt_hours}h</strong></span>
        </div>
        <div class="lt-pillar-insight">${p.sleep.insight}</div>
        <div class="lt-pillar-evidence-box">🔬 מחקר: ${p.sleep.citation}</div>
        <div class="lt-pillar-action-box">👉 ${p.sleep.action}</div>
      </div>

      <!-- Pillar 5: Training Stimulus -->
      <div class="lt-pillar-card">
        <div class="lt-pillar-top">
          <div class="lt-pillar-title-wrap">
            <span class="lt-pillar-icon">⚔️</span>
            <span class="lt-pillar-title">${p.training.title}</span>
          </div>
          <span class="lt-pillar-badge ${p.training.badge_type}">${p.training.badge}</span>
        </div>
        <div class="lt-pillar-stats-row">
          <span class="lt-stat-chip">אימונים שבוצעו: <strong>${p.training.total_workouts}</strong></span>
          <span class="lt-stat-chip">קצב שבועי: <strong>${p.training.weekly_frequency} אימונים/שבוע</strong></span>
        </div>
        <div class="lt-pillar-insight">${p.training.insight}</div>
        <div class="lt-pillar-evidence-box">🔬 מחקר: ${p.training.citation}</div>
        <div class="lt-pillar-action-box">👉 ${p.training.action}</div>
      </div>
    `;
  },

  // ==========================================
  // HUNTER SKILLS & WORKOUT ENGINE
  // ==========================================
  async fetchSkills() {
    try {
      const res = await fetch('/api/skills');
      const data = await res.json();
      this.skills = data.skills || [];
      this.renderSkills();
    } catch (e) {
      console.warn('Could not fetch skills:', e);
    }
  },

  renderSkills() {
    const grid = document.getElementById('skills-grid');
    if (!grid) return;

    if (!this.skills || this.skills.length === 0) {
      grid.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:12px; color:var(--text-dim); font-size:12px;">טוען יכולות צייד...</div>`;
      return;
    }

    grid.innerHTML = this.skills.map(s => {
      const code = s.skill_code || s.code;
      const curExp = s.current_exp !== undefined ? s.current_exp : (s.exp || 0);
      const nextExp = s.exp_to_next || 100;
      const pct = Math.min(100, Math.round((curExp / nextExp) * 100));
      const statType = s.stat_boost_type || (code === 'colossus_strength' ? 'STR' : (code === 'shadow_sprint' ? 'AGI' : (code === 'nutrition_mastery' ? 'INT' : (code === 'regeneration' ? 'VIT' : 'PER'))));
      const statBoost = s.stat_boost_val || 2;
      const bonusText = `${statType} +${s.level * statBoost}`;
      const desc = s.description_he || s.desc_he || '';

      return `
        <div class="skill-card" data-code="${code}">
          <div class="skill-top-row">
            <div class="skill-icon-name">
              <span class="skill-icon">${s.icon || '⚡'}</span>
              <div>
                <div class="skill-name">${s.name_he}</div>
                <div class="skill-name-en">${s.name_en || code}</div>
              </div>
            </div>
            <div class="skill-level-badge">Lv. ${s.level}</div>
          </div>
          <div class="skill-desc">${desc}</div>
          <div class="skill-progress-bar-wrap">
            <div class="skill-progress-bar" style="width: ${pct}%;"></div>
          </div>
          <div class="skill-bottom-row">
            <span class="skill-bonus-tag">⚡ ${bonusText}</span>
            <span class="skill-exp-text">${curExp} / ${nextExp} XP (${pct}%)</span>
          </div>
        </div>
      `;
    }).join('');
  },

  openWorkoutModal() {
    sfx.playClick();
    this.openModal('workout-modal');
  },

  onWorkoutTypeChange() {
    const sel = document.getElementById('workout-type-select').value;
    const titleInput = document.getElementById('workout-title-input');
    const durInput = document.getElementById('workout-duration-input');
    const calInput = document.getElementById('workout-calories-input');

    if (sel === 'strength') {
      titleInput.value = 'אימון כוח (Hypertrophy)';
      durInput.value = 50;
      calInput.value = 350;
    } else if (sel === 'run') {
      titleInput.value = 'ריצה / ספרינטים';
      durInput.value = 30;
      calInput.value = 320;
    } else if (sel === 'cardio') {
      titleInput.value = 'אירובי / אופניים';
      durInput.value = 40;
      calInput.value = 300;
    } else if (sel === 'hiit') {
      titleInput.value = 'אימון הפוגות / קרוספיט';
      durInput.value = 30;
      calInput.value = 350;
    }
  },

  async saveWorkoutLog() {
    sfx.playClick();
    const wType = document.getElementById('workout-type-select').value;
    const title = document.getElementById('workout-title-input').value.trim() || 'אימון צייד';
    const duration = parseInt(document.getElementById('workout-duration-input').value) || 45;
    const calories = parseInt(document.getElementById('workout-calories-input').value) || 300;
    const notes = document.getElementById('workout-notes-input').value.trim();

    try {
      const res = await fetch('/api/workouts/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workout_type: wType,
          title: title,
          duration_min: duration,
          calories_burned: calories,
          notes: notes
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'שגיאת שרת ברישום האימון');
      }
      this.closeModal('workout-modal');
      sfx.playSystemNotification();
      this.showToast(`[SYSTEM: אימון נרשם בהצלחה!]`);

      // Check skill leveling up
      if (data.skill_leveling && data.skill_leveling.leveled_up) {
        this.showSkillLevelUpModal(data.skill_leveling);
      }

      if (data.newly_unlocked_achievements && data.newly_unlocked_achievements.length > 0) {
        this.checkNewlyUnlocked(data.newly_unlocked_achievements);
      }

      await this.fetchSkills();
      await this.fetchTodayData();
      await this.fetchDailyDebrief();
    } catch (e) {
      console.error('Error in saveWorkoutLog:', e);
      alert('שגיאה ברישום האימון: ' + (e.message || e));
    }
  },

  showSkillLevelUpModal(event) {
    const overlay = document.getElementById('skill-levelup-overlay');
    if (!overlay) return;

    const iconEl = document.getElementById('skill-levelup-icon');
    const titleEl = document.getElementById('skill-levelup-title');
    const valEl = document.getElementById('skill-levelup-val');
    const rewardEl = document.getElementById('skill-levelup-reward');

    const defaultIcons = {
      'nutrition_mastery': '🍖',
      'colossus_strength': '⚔️',
      'shadow_sprint': '⚡',
      'alchemy_discipline': '🧪'
    };

    if (iconEl) iconEl.innerText = event.skill?.icon || defaultIcons[event.skill_code] || '⚡';
    if (titleEl) titleEl.innerText = event.name_he || event.skill?.name_he || 'יכולת צייד';
    if (valEl) valEl.innerText = event.level || event.skill?.level || 2;
    if (rewardEl) {
      const statGain = event.stat_boost_val || event.stat_awarded || 2;
      const statType = event.stat_boost_type || event.stat_type || 'STR';
      rewardEl.innerText = `בונוס תכונה שודרג: +${statGain} ל-${statType}!`;
    }

    overlay.style.display = 'flex';
    sfx.playLevelUp();

    setTimeout(() => {
      overlay.style.display = 'none';
    }, 3500);
  },

  // ==========================================
  // HUNTER ALCHEMY & SUPPLEMENTS TRACKER
  // ==========================================
  async fetchSupplements() {
    try {
      const res = await fetch('/api/supplements/today');
      const data = await res.json();
      this.supplements = data.supplements || [];
      this.renderSupplements();
    } catch (e) {
      console.warn('Could not fetch supplements:', e);
    }
  },

  renderSupplements() {
    const list = document.getElementById('supplements-today-list');
    if (!list) return;

    if (!this.supplements || this.supplements.length === 0) {
      list.innerHTML = `
        <div style="padding:14px; text-align:center; color:var(--text-dim); font-size:12px; background:rgba(255,255,255,0.02); border-radius:8px; border:1px dashed rgba(255,255,255,0.08);">
          💊 טרם נרשמו ויטמינים או תוספים להיום. לחץ על הלחצנים המהירים למעלה לרישום בלחיצה אחת!
        </div>
      `;
      return;
    }

    const catIcons = {
      'vitamin': '🌿',
      'mineral': '🌙',
      'omega': '🐟',
      'performance': '💥'
    };

    list.innerHTML = this.supplements.map(item => `
      <div class="supp-item-card">
        <div class="supp-item-left">
          <span class="supp-item-icon">${catIcons[item.category] || '🧪'}</span>
          <div>
            <div class="supp-item-name">${item.name}</div>
            <div class="supp-item-dosage">${item.dosage} ${item.unit && item.unit !== 'dose' ? item.unit : ''} • ${item.timestamp || ''}</div>
          </div>
        </div>
        <button class="supp-item-delete" onclick="AppState.deleteSupplement(${item.id})" title="מחק תוסף">✕</button>
      </div>
    `).join('');
  },

  async quickAddSupplement(name, dose, category) {
    sfx.playClick();
    try {
      const res = await fetch('/api/supplements/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          dosage: dose,
          unit: 'dose',
          category: category
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'שגיאת שרת ברישום התוסף');
      }
      sfx.playPotion();
      this.showToast(`[SYSTEM: ${name} נרשם בהצלחה!]`);

      if (data.skill_leveling && data.skill_leveling.leveled_up) {
        this.showSkillLevelUpModal(data.skill_leveling);
      }

      await this.fetchSupplements();
      await this.fetchSkills();
      await this.fetchDailyDebrief();
      await this.fetchTodayData();
    } catch (e) {
      console.error('Error in quickAddSupplement:', e);
      alert('שגיאה ברישום התוסף: ' + (e.message || e));
    }
  },

  openSupplementModal() {
    sfx.playClick();
    document.getElementById('custom-supp-name').value = '';
    document.getElementById('custom-supp-dose').value = '';
    this.openModal('supplement-modal');
  },

  async saveCustomSupplement() {
    sfx.playClick();
    const name = document.getElementById('custom-supp-name').value.trim();
    if (!name) {
      alert('נא להזין שם תוסף או ויטמין');
      return;
    }
    const dose = document.getElementById('custom-supp-dose').value.trim() || '1 מנה';
    const cat = document.getElementById('custom-supp-category').value;

    try {
      const res = await fetch('/api/supplements/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name,
          dosage: dose,
          unit: 'dose',
          category: cat
        })
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'שגיאת שרת ברישום התוסף');
      }
      this.closeModal('supplement-modal');
      sfx.playPotion();
      this.showToast(`[SYSTEM: ${name} נרשם בהצלחה!]`);

      if (data.skill_leveling && data.skill_leveling.leveled_up) {
        this.showSkillLevelUpModal(data.skill_leveling);
      }

      await this.fetchSupplements();
      await this.fetchSkills();
      await this.fetchDailyDebrief();
      await this.fetchTodayData();
    } catch (e) {
      console.error('Error in saveCustomSupplement:', e);
      alert('שגיאה ברישום התוסף: ' + (e.message || e));
    }
  },

  async deleteSupplement(id) {
    sfx.playClick();
    try {
      await fetch(`/api/supplements/log/${id}`, { method: 'DELETE' });
      sfx.playSystemNotification();
      await this.fetchSupplements();
      await this.fetchDailyDebrief();
    } catch (e) {
      alert('שגיאה במחיקת התוסף');
    }
  },

  // ==========================================
  // EVIDENCE-BASED DAILY HEALTH SYNERGY DEBRIEF
  // ==========================================
  async fetchDailyDebrief() {
    try {
      const res = await fetch('/api/health-synergy/daily-debrief');
      const data = await res.json();
      this.dailyDebrief = data;
      this.renderDailyDebrief();
    } catch (e) {
      console.warn('Could not fetch daily debrief:', e);
    }
  },

  renderDailyDebrief() {
    if (!this.dailyDebrief) return;
    const d = this.dailyDebrief;

    const scoreValEl = document.getElementById('debrief-score-val');
    const titleEl = document.getElementById('debrief-status-title');
    const subEl = document.getElementById('debrief-status-sub');
    const scoreCard = document.getElementById('debrief-score-card');

    if (scoreValEl) scoreValEl.innerText = d.composite_score ?? 85;
    if (titleEl) titleEl.innerText = d.status_title || 'סינרגיה פיזיולוגית תקינה';
    if (subEl) subEl.innerText = d.status_sub || 'הצלבת מדדי Garmin, תזונה, אטנט, ויטמינים ומשמרת';

    if (scoreCard) {
      const score = d.composite_score || 80;
      if (score >= 80) {
        scoreCard.style.borderColor = 'rgba(16,185,129,0.4)';
        if (scoreValEl) scoreValEl.style.color = 'var(--neon-green)';
      } else if (score >= 60) {
        scoreCard.style.borderColor = 'rgba(245,158,11,0.4)';
        if (scoreValEl) scoreValEl.style.color = '#fbbf24';
      } else {
        scoreCard.style.borderColor = 'rgba(239,68,68,0.4)';
        if (scoreValEl) scoreValEl.style.color = '#f87171';
      }
    }

    this.renderDebriefTabContent();
  },

  switchDebriefTab(tab) {
    sfx.playClick();
    this.activeDebriefTab = tab;
    ['maintain', 'improve', 'status', 'research'].forEach(t => {
      const btn = document.getElementById(`tab-btn-${t}`);
      if (btn) {
        if (t === tab) btn.classList.add('active');
        else btn.classList.remove('active');
      }
    });
    this.renderDebriefTabContent();
  },

  renderDebriefTabContent() {
    const container = document.getElementById('debrief-tab-content');
    if (!container || !this.dailyDebrief) return;
    const d = this.dailyDebrief;

    if (this.activeDebriefTab === 'maintain') {
      const list = d.maintain_list || [];
      if (list.length === 0) {
        container.innerHTML = `<div style="padding:14px; text-align:center; color:var(--text-dim); font-size:12px;">טרם נרשמו נקודות חוזק להיום.</div>`;
        return;
      }
      container.innerHTML = list.map(item => `
        <div class="debrief-item-card maintain">
          <div class="debrief-item-header">
            <span class="debrief-item-title">🛡️ ${item.title}</span>
            <span class="debrief-item-tag science">${item.tag || 'שימור'}</span>
          </div>
          <div class="debrief-item-desc">${item.desc}</div>
        </div>
      `).join('');
    } else if (this.activeDebriefTab === 'improve') {
      const list = d.improve_list || [];
      if (list.length === 0) {
        container.innerHTML = `
          <div class="debrief-item-card maintain">
            <div class="debrief-item-header">
              <span class="debrief-item-title">👑 מושלם! אין ליקויים לתיקון</span>
              <span class="debrief-item-tag science">OPTIMAL</span>
            </div>
            <div class="debrief-item-desc">כל המדדים (קלוריות, חלבון, רוויה, תוספים ואיזון מערכת העצבים) במצב מעולה להיום!</div>
          </div>
        `;
        return;
      }
      container.innerHTML = list.map(item => `
        <div class="debrief-item-card improve">
          <div class="debrief-item-header">
            <span class="debrief-item-title">🎯 ${item.title}</span>
            <span class="debrief-item-tag alert">${item.tag || 'לשיפור'}</span>
          </div>
          <div class="debrief-item-desc">${item.desc}</div>
        </div>
      `).join('');
    } else if (this.activeDebriefTab === 'status') {
      const analysis = d.status_analysis || [];
      container.innerHTML = analysis.map(st => `
        <div class="debrief-item-card status">
          <div class="debrief-item-header">
            <span class="debrief-item-title">${st.icon || '📊'} ${st.domain}</span>
            <span class="debrief-item-tag ${st.status_level === 'optimal' ? 'science' : (st.status_level === 'warning' ? 'alert' : 'info')}">${st.status_label}</span>
          </div>
          <div class="debrief-item-desc">${st.summary}</div>
        </div>
      `).join('');
    } else if (this.activeDebriefTab === 'research') {
      const citations = d.research_citations || [];
      container.innerHTML = citations.map(c => `
        <div class="debrief-item-card research">
          <div class="debrief-item-header">
            <span class="debrief-item-title">🔬 ${c.title}</span>
            <span class="debrief-item-tag science">${c.source}</span>
          </div>
          <div class="debrief-item-desc">
            <strong>ממצא מפתח:</strong> ${c.finding}
          </div>
          <div style="font-size:11px; color:#38bdf8; margin-top:4px;">
            <strong>יישום במערכת:</strong> ${c.system_application}
          </div>
        </div>
      `).join('');
    }
  },

  // ========================================================
  // ACHIEVEMENTS & TROPHIES ENGINE (Matching Image 2)
  // ========================================================
  async fetchAchievements() {
    try {
      const res = await fetch('/api/achievements');
      if (res.ok) {
        const data = await res.json();
        this.achievements = data.achievements || [];
        localStorage.setItem('hunter_achievements', JSON.stringify(this.achievements));
        this.renderAchievements();
        this.updateBadgePills(data.unlocked_count, data.total_count);
      }
    } catch (e) {
      console.warn('Could not fetch achievements, using cache:', e);
      const cached = localStorage.getItem('hunter_achievements');
      if (cached) {
        try {
          this.achievements = JSON.parse(cached);
          this.renderAchievements();
        } catch (err) {}
      }
    }
  },

  updateBadgePills(unlocked, total) {
    const pill = document.getElementById('badges-pill-count');
    if (pill) pill.innerText = `${unlocked}/${total}`;
    const navPill = document.getElementById('nav-badge-pill');
    if (navPill) navPill.innerText = unlocked;
  },

  renderAchievements() {
    const grid = document.getElementById('achievements-hex-grid');
    if (!grid || !this.achievements) return;

    const unlocked = this.achievements.filter(a => a.unlocked);
    const total = this.achievements.length;
    const pct = total > 0 ? Math.round((unlocked.length / total) * 100) : 0;

    const countText = document.getElementById('ach-unlocked-count-text');
    if (countText) countText.innerText = `${unlocked.length} / ${total} פתוחים (${pct}%)`;

    const fillBar = document.getElementById('ach-mini-prog-fill');
    if (fillBar) fillBar.style.width = `${pct}%`;

    this.updateBadgePills(unlocked.length, total);

    grid.innerHTML = this.achievements.map(ach => {
      const isUnlocked = ach.unlocked;
      const tierColor = ach.tier_color || 'gold';
      if (isUnlocked) {
        const escapedJson = JSON.stringify(ach).replace(/"/g, '&quot;');
        return `
          <div class="ach-hex-card unlocked" onclick="AppState.showAchievementOverlay(${escapedJson})">
            <div class="ach-hex-badge unlocked ${tierColor}">
              <span class="ach-hex-icon">${ach.icon || '🏆'}</span>
            </div>
            <div class="ach-card-title">${ach.title}</div>
            <div class="ach-card-desc">${ach.description}</div>
            <div class="ach-card-reward">${ach.reward_desc || ''}</div>
            <div class="ach-unlocked-date">✓ פתוח (${ach.unlocked_at ? ach.unlocked_at.split(' ')[0] : 'היום'})</div>
          </div>
        `;
      } else {
        return `
          <div class="ach-hex-card locked" title="הישג נעול: ${ach.description}">
            <div class="ach-hex-badge locked">
              <span>?</span>
            </div>
            <div class="ach-card-title">${ach.title}</div>
            <div class="ach-card-desc">${ach.description}</div>
            <div class="ach-card-reward">${ach.reward_desc || ''}</div>
          </div>
        `;
      }
    }).join('');
  },

  openAchievementsModal() {
    this.navTo('badges');
    this.switchBadgesSubtab('achievements');
  },

  showAchievementOverlay(ach) {
    const overlay = document.getElementById('achievement-unlocked-overlay');
    if (!overlay) return;
    const iconEl = document.getElementById('ach-unlocked-icon');
    if (iconEl) iconEl.innerText = ach.icon || '🏆';
    const hexBadge = document.getElementById('ach-unlocked-hex');
    if (hexBadge) hexBadge.className = `ach-hex-badge unlocked ${ach.tier_color || 'gold'}`;
    const titleEl = document.getElementById('ach-unlocked-title');
    if (titleEl) titleEl.innerText = ach.title;
    const descEl = document.getElementById('ach-unlocked-desc');
    if (descEl) descEl.innerText = ach.description;
    const rewardEl = document.getElementById('ach-unlocked-reward');
    if (rewardEl) rewardEl.innerText = ach.reward_desc || '+EXP';

    sfx.playLevelUp();
    overlay.classList.add('active');
  },

  closeAchievementOverlay() {
    const overlay = document.getElementById('achievement-unlocked-overlay');
    if (overlay) overlay.classList.remove('active');
  },

  checkNewlyUnlocked(newlyUnlockedList) {
    if (Array.isArray(newlyUnlockedList) && newlyUnlockedList.length > 0) {
      newlyUnlockedList.forEach((ach, i) => {
        setTimeout(() => {
          this.showAchievementOverlay(ach);
          this.fetchAchievements();
        }, i * 3500);
      });
    }
  },

  // ========================================================
  // RANK CONSTELLATION & SYSTEM (Matching Image 4)
  // ========================================================
  openRankModal() {
    this.navTo('badges');
    this.switchBadgesSubtab('ranks');
  },

  renderRankModal() {
    if (!this.profile) return;
    const p = this.profile;
    const curLevel = p.level || 1;
    const curRank = (p.rank || 'E-Rank').replace('-Rank', '').replace('Rank', '').trim();

    const ranks = [
      { key: 'E', name: 'E-Rank', title: 'צייד שהתעורר', min: 1, max: 9, classKey: 'rank-e', perk: 'גישה למערכת המשימות' },
      { key: 'D', name: 'D-Rank', title: 'לוחם טירון', min: 10, max: 19, classKey: 'rank-d', perk: '+5% בונוס צבירת XP' },
      { key: 'C', name: 'C-Rank', title: 'צייד מנוסה', min: 20, max: 29, classKey: 'rank-c', perk: '+10% בונוס התאוששות' },
      { key: 'B', name: 'B-Rank', title: 'לוחם מובחר', min: 30, max: 39, classKey: 'rank-b', perk: 'חסינות עייפות מוגברת' },
      { key: 'A', name: 'A-Rank', title: 'צייד עלית', min: 40, max: 49, classKey: 'rank-a', perk: '+15% לפוקוס ואנרגיה' },
      { key: 'S', name: 'S-Rank', title: 'אגדה חיה (S-Rank)', min: 50, max: 74, classKey: 'rank-s', perk: 'הילת זהב • +25% כוח וסיבולת' },
      { key: 'SS', name: 'SS-Rank', title: 'שליט צללים עליון', min: 75, max: 99, classKey: 'rank-ss', perk: 'זרימת מאנה מקסימלית' },
      { key: 'SSS', name: 'Shadow Monarch', title: 'מונרך הצללים (SSS)', min: 100, max: 999, classKey: 'rank-sss', perk: 'שליטה מוחלטת • עוצמה אינסופית' }
    ];

    // Current hero hex
    const heroHex = document.getElementById('rank-hero-hex');
    const heroLetter = document.getElementById('rank-hero-letter');
    const heroTitle = document.getElementById('rank-hero-title-text');
    const heroRange = document.getElementById('rank-hero-level-range');
    const heroNext = document.getElementById('rank-hero-next-label');
    const heroBar = document.getElementById('rank-hero-bar-fill');

    const curRankObj = ranks.find(r => r.key === curRank) || ranks[0];
    const nextRankObj = ranks.find(r => r.min > curLevel) || null;

    if (heroHex) {
      heroHex.className = `rank-hex-hero ${curRankObj.classKey}`;
    }
    if (heroLetter) heroLetter.innerText = curRankObj.key;
    if (heroTitle) heroTitle.innerText = `${p.name || 'רום'} • ${curRankObj.title}`;
    if (heroRange) heroRange.innerText = `רמה ${curLevel} (טווח רנק: ${curRankObj.min}-${curRankObj.max})`;

    if (nextRankObj) {
      const levelsNeeded = nextRankObj.min - curLevel;
      const levelsInCurrent = nextRankObj.min - curRankObj.min;
      const progressInRank = Math.min(100, Math.max(0, Math.round(((curLevel - curRankObj.min) / Math.max(1, levelsInCurrent)) * 100)));
      if (heroNext) heroNext.innerText = `${nextRankObj.name} (רמה ${nextRankObj.min}, נותרו ${levelsNeeded} רמות)`;
      if (heroBar) heroBar.style.width = `${progressInRank}%`;
    } else {
      if (heroNext) heroNext.innerText = 'הגעת לדרגת שיא עליונה (Shadow Monarch)!';
      if (heroBar) heroBar.style.width = '100%';
    }

    // Constellation Grid
    const constellationGrid = document.getElementById('rank-constellation-grid');
    if (constellationGrid) {
      constellationGrid.innerHTML = ranks.map(r => {
        let status = 'locked';
        let statusTag = '🔒 נעול';
        if (curRank === r.key) {
          status = 'active';
          statusTag = '⚡ נוכחי';
        } else if (curLevel >= r.min) {
          status = 'unlocked';
          statusTag = '✓ פתוח';
        }

        return `
          <div class="rank-constellation-item ${status}">
            <div class="rank-item-hex ${r.classKey}">${r.key}</div>
            <div class="rank-item-title">${r.name}</div>
            <div class="rank-item-level">רמה ${r.min}+</div>
            <span class="rank-item-status-tag">${statusTag}</span>
          </div>
        `;
      }).join('');
    }
  },

  shareRank() {
    if (!this.profile) return;
    const p = this.profile;
    const text = `⚔️ SOLO LEVELING: THE SYSTEM ⚔️\nצייד: ${p.name || 'רום'}\nדרגה: ${p.rank} | רמה: ${p.level}\nתואר: ${p.title}\nמזהה: ${p.hunter_id || 'HNT-77492'}\nARISE - Rise to SSS-Rank!`;
    
    if (navigator.share) {
      navigator.share({
        title: 'Solo Leveling Hunter Card',
        text: text
      }).catch(() => {});
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        alert('📋 כרטיס הצייד הועתק ללוח!');
      });
    } else {
      alert(text);
    }
  },

  copyHunterId() {
    const id = document.getElementById('hunter-system-id')?.innerText || 'HNT-77492';
    if (navigator.clipboard) {
      navigator.clipboard.writeText(id).then(() => {
        const btn = document.querySelector('.copy-id-btn');
        if (btn) {
          const old = btn.innerText;
          btn.innerText = '✓';
          setTimeout(() => btn.innerText = old, 1500);
        }
      });
    }
  },

  scrollToSection(id) {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  },

  navTo(section) {
    // 1. Update active tab panel
    const panels = document.querySelectorAll('.tab-panel');
    panels.forEach(p => p.classList.remove('active'));
    const targetPanel = document.getElementById(`panel-${section}`);
    if (targetPanel) {
      targetPanel.classList.add('active');
    }

    // 2. Update active nav button
    document.querySelectorAll('.bottom-nav-item').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`nav-item-${section}`);
    if (btn) btn.classList.add('active');

    // 3. Scroll to top of the panel smoothly
    window.scrollTo({ top: 0, behavior: 'instant' });
    sfx.playClick();

    // 4. Panel specific refreshes
    if (section === 'badges') {
      this.renderAchievements();
      this.renderRankModal();
    } else if (section === 'quests') {
      this.renderQuests();
    } else if (section === 'workouts') {
      this.renderSkills();
    } else if (section === 'nutrition') {
      this.renderCalorieGauge();
      this.renderMacroBars();
      this.renderMicronutrients();
      this.renderMealsList();
    } else if (section === 'health') {
      this.renderGarminBiometrics();
      this.renderAttentBanner();
      this.renderSupplements();
      this.renderDailyDebrief();
    }
  },

  switchBadgesSubtab(subtab) {
    sfx.playClick();
    const btnAch = document.getElementById('subtab-btn-achievements');
    const btnRank = document.getElementById('subtab-btn-ranks');
    const viewAch = document.getElementById('subtab-view-achievements');
    const viewRank = document.getElementById('subtab-view-ranks');

    if (subtab === 'achievements') {
      if (btnAch) btnAch.classList.add('active');
      if (btnRank) btnRank.classList.remove('active');
      if (viewAch) viewAch.style.display = 'block';
      if (viewRank) viewRank.style.display = 'none';
      this.renderAchievements();
    } else {
      if (btnRank) btnRank.classList.add('active');
      if (btnAch) btnAch.classList.remove('active');
      if (viewRank) viewRank.style.display = 'block';
      if (viewAch) viewAch.style.display = 'none';
      this.renderRankModal();
    }
  }
};

window.addEventListener('DOMContentLoaded', () => {
  AppState.init();
});
