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
  waterLogs: [],
  achievements: [],
  totalWorkouts: 0,
  achievementsSummary: null,
  dailyDebrief: null,
  activeDebriefTab: 'maintain',
  codeReader: null,
  customAIGoals: null,
  aiConsultHistory: [],
  aiRecommendations: [],
  currentQuickBioField: 'height',

  async init() {
    // Setup Service Worker with force update
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/service-worker.js?v=23').then((reg) => {
        reg.update();
      }).catch(console.error);
    }

    // Load sound toggle state
    this.updateSoundBtnUI();

    // Initialize Offline-First Queue
    this.initOfflineQueue();

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
    await this.fetchAIRecommendations();

    // Setup input listeners
    this.bindEvents();

    // Check disaster recovery & auto snapshotting
    this.checkDisasterRecovery();
    this.saveLocalSnapshot();
    this.updateBackupUI();

    // Check first-time awakening onboarding
    this.checkFirstTimeAwakening();

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
      this.waterLogs = data.water_logs || [];
      if (data.supplements) this.supplements = data.supplements;
      if (data.total_workouts !== undefined) {
        this.totalWorkouts = data.total_workouts;
      }
      if (data.achievements_summary) {
        this.achievementsSummary = data.achievements_summary;
        const u = data.achievements_summary.unlocked_count ?? data.achievements_summary.unlocked ?? 0;
        const t = data.achievements_summary.total_count ?? data.achievements_summary.total ?? 0;
        this.updateBadgePills(u, t);
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
    this.renderWaterCockpit();
    this.renderQuests();
    this.renderMicronutrients();
    this.renderMealsList();
    if (this.longTermData) this.renderLongTermInsights(this.longTermData);
    this.renderAIRecommendations();
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
    if (heightEl) heightEl.innerText = `${p.height || 180} cm`;

    const weightEl = document.getElementById('char-bio-weight');
    if (weightEl) weightEl.innerText = `${Number(p.weight || 83).toFixed(1)} kg`;

    const ageEl = document.getElementById('char-bio-age');
    if (ageEl) ageEl.innerText = p.age || 26;

    const targetEl = document.getElementById('char-bio-target');
    if (targetEl) targetEl.innerText = `${Number(p.target_weight || 87).toFixed(1)} kg`;

    const hunterIdEl = document.getElementById('hunter-system-id');
    if (hunterIdEl) {
      const seed = Math.abs((p.name || 'ROM').split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 77000)) % 100000;
      hunterIdEl.innerText = p.hunter_id || `HNT-${String(seed).padStart(5, '0')}`;
    }

    // Render Active AI Goal Directives Card on Profile
    const aiGoalCard = document.getElementById('active-ai-goal-card');
    if (aiGoalCard) {
      const hasAiGoals = p.ai_analysis_headline || p.ai_explanation || p.goal_custom_text;
      if (hasAiGoals) {
        aiGoalCard.style.display = 'block';
        aiGoalCard.innerHTML = `
          <div class="ai-goal-card-header">
            <div class="ai-goal-card-badge">⚡ הנחיות מערכת AI פעילות</div>
            <button type="button" class="ai-goal-edit-btn" onclick="AppState.openFirstTimeAwakening(true)" title="עדכון מטרות ויעדים עם AI">
              ✏️ עדכן יעדים
            </button>
          </div>
          
          <div class="ai-goal-headline">🎯 ${this.escapeHtml(p.ai_analysis_headline || 'מפרט מדעי מותאם אישית')}</div>

          ${p.goal_custom_text ? `
            <div class="ai-goal-user-prompt">
              <span class="ai-gup-label">🎯 מטרת העל שהגדרת לצ'אט:</span>
              <span class="ai-gup-text">"${this.escapeHtml(p.goal_custom_text)}"</span>
            </div>
          ` : ''}

          ${p.ai_explanation ? `
            <div class="ai-goal-explanation">${this.escapeHtml(p.ai_explanation)}</div>
          ` : ''}

          <div class="ai-goal-targets-row">
            <div class="ai-gt-chip"><span class="ai-gt-label">יעד קלוריות</span><span class="ai-gt-val highlight">${p.target_calories ? p.target_calories.toLocaleString() : '--'} kcal</span></div>
            <div class="ai-gt-chip"><span class="ai-gt-label">חלבון יומי</span><span class="ai-gt-val">${p.target_protein || '--'}g</span></div>
            <div class="ai-gt-chip"><span class="ai-gt-label">פחמימות</span><span class="ai-gt-val">${p.target_carbs || '--'}g</span></div>
            <div class="ai-gt-chip"><span class="ai-gt-label">שומנים</span><span class="ai-gt-val">${p.target_fats || '--'}g</span></div>
            <div class="ai-gt-chip"><span class="ai-gt-label">מים יומי</span><span class="ai-gt-val">${p.target_water ? p.target_water.toLocaleString() : '--'} ml</span></div>
            <div class="ai-gt-chip"><span class="ai-gt-label">משקל יעד</span><span class="ai-gt-val highlight">${p.target_weight ? Number(p.target_weight).toFixed(1) : '--'} kg</span></div>
          </div>

          ${p.ai_hunter_tip ? `
            <div class="ai-goal-tip-box">
              💡 <strong>המלצת המערכת:</strong> ${this.escapeHtml(p.ai_hunter_tip)}
            </div>
          ` : ''}
        `;
      } else {
        aiGoalCard.style.display = 'none';
      }
    }

    // Render Nutrition Tab AI Directives Banner
    const nutAiBanner = document.getElementById('nutrition-ai-goal-banner');
    if (nutAiBanner) {
      if (p.ai_analysis_headline || p.goal_custom_text) {
        nutAiBanner.style.display = 'flex';
        nutAiBanner.innerHTML = `
          <div class="nut-ai-icon">⚡</div>
          <div class="nut-ai-content">
            <div class="nut-ai-title">${this.escapeHtml(p.ai_analysis_headline || 'פרוטוקול AI מותאם אישית פעיל')}</div>
            <div class="nut-ai-desc">${this.escapeHtml(p.goal_custom_text ? `יעד: "${p.goal_custom_text}"` : (p.ai_hunter_tip || ''))}</div>
          </div>
          <button type="button" class="nut-ai-btn" onclick="AppState.openFirstTimeAwakening(true)">התאם יעדים</button>
        `;
      } else {
        nutAiBanner.style.display = 'none';
      }
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

  renderWaterCockpit() {
    if (!this.profile || !this.consumed) return;
    const p = this.profile;
    const c = this.consumed;
    const curWater = Math.round(c.water_ml || 0);
    const tgtWater = Math.round(p.target_water || 3000);
    const pct = Math.min(100, Math.round((curWater / Math.max(1, tgtWater)) * 100));

    const curEl = document.getElementById('water-cur-amount');
    if (curEl) curEl.innerText = curWater.toLocaleString();

    const tgtEl = document.getElementById('water-tgt-amount');
    if (tgtEl) tgtEl.innerText = tgtWater.toLocaleString();

    const badgeEl = document.getElementById('water-pct-badge');
    if (badgeEl) badgeEl.innerText = `${pct}%`;

    const waveEl = document.getElementById('water-wave-fill');
    if (waveEl) waveEl.style.height = `${pct}%`;

    const remEl = document.getElementById('water-remaining-text');
    if (remEl) {
      if (curWater >= tgtWater) {
        remEl.innerText = '🏆 יעד המים היומי הושלם בהצלחה!';
        remEl.style.color = '#38bdf8';
      } else {
        const remaining = tgtWater - curWater;
        remEl.innerText = `נותרו ${remaining.toLocaleString()} מ״ל ליעד`;
        remEl.style.color = '#94a3b8';
      }
    }

    // Water logs mini list
    const listEl = document.getElementById('water-logs-mini-list');
    const countEl = document.getElementById('water-logs-count');
    if (countEl) countEl.innerText = this.waterLogs ? this.waterLogs.length : 0;

    if (listEl) {
      if (!this.waterLogs || this.waterLogs.length === 0) {
        listEl.innerHTML = '<div style="color:var(--text-muted); font-size:11px; text-align:center; padding:8px;">אין עדיין לגימות או משקאות רשומים היום</div>';
      } else {
        listEl.innerHTML = this.waterLogs.map(l => `
          <div class="water-log-chip">
            <span class="water-log-bev">${l.beverage_icon || '💧'} ${l.beverage_name || 'מים'}</span>
            <span class="water-log-time">🕒 ${l.timestamp || '--:--'}</span>
            <span class="water-log-vol">+${l.amount_ml} מ״ל</span>
            <button class="water-log-del-btn" onclick="AppState.deleteWaterLog(${l.id})" title="מחק רישום זה">✕</button>
          </div>
        `).join('');
      }
    }
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
    const suppM = c.supp_micros || {};

    const micros = [
      { name: 'מים (רוויה)', cur: c.water_ml, tgt: p.target_water, unit: 'ml', icon: '💧', suppBonus: 0 },
      { name: 'סיבים תזונתיים', cur: Math.round(c.fiber), tgt: p.target_fiber, unit: 'g', icon: '🌾', suppBonus: 0 },
      { name: 'מגנזיום (התאוששות)', cur: Math.round(c.magnesium_mg), tgt: 400, unit: 'mg', icon: '🌙', suppBonus: suppM.magnesium_mg || 0 },
      { name: 'אבץ (מערכת חיסון)', cur: Math.round(c.zinc_mg), tgt: 15, unit: 'mg', icon: '🛡️', suppBonus: suppM.zinc_mg || 0 },
      { name: 'ויטמין C (נוגד חמצון)', cur: Math.round(c.vit_c_mg), tgt: 90, unit: 'mg', icon: '🍊', suppBonus: suppM.vit_c_mg || 0 },
      { name: 'אשלגן (אלקטרוליטים)', cur: Math.round(c.potassium_mg), tgt: 3500, unit: 'mg', icon: '⚡', suppBonus: suppM.potassium_mg || 0 },
      { name: 'ויטמין D3 (צפיפות ועצבים)', cur: Math.round(c.vit_d_iu || 0), tgt: 1500, unit: 'IU', icon: '☀️', suppBonus: suppM.vit_d_iu || 0 },
      { name: 'אומגה 3 (EPA/DHA)', cur: Math.round(c.omega3_mg || 0), tgt: 1000, unit: 'mg', icon: '🐟', suppBonus: suppM.omega3_mg || 0 }
    ];

    const gridEl = document.getElementById('micro-grid');
    if (!gridEl) return;
    gridEl.innerHTML = '';

    micros.forEach(m => {
      const pct = Math.min(100, Math.round((m.cur / Math.max(1, m.tgt)) * 100));
      const item = document.createElement('div');
      item.className = 'micro-item';
      if (m.suppBonus > 0) item.classList.add('micro-has-supp');

      const suppBadgeHtml = m.suppBonus > 0 
        ? `<span class="micro-supp-tag" title="מתוכם ${Math.round(m.suppBonus)} ${m.unit} מתוספים/ויטמינים">🧪 +${Math.round(m.suppBonus)}${m.unit} תוסף</span>` 
        : '';

      item.innerHTML = `
        <div class="micro-top">
          <span class="micro-name">${m.icon} ${m.name}</span>
          <div style="display:flex; align-items:center; gap:4px;">
            ${suppBadgeHtml}
            <span class="micro-vals">${m.cur}/${m.tgt} ${m.unit} (${pct}%)</span>
          </div>
        </div>
        <div class="micro-track">
          <div class="micro-fill" style="width: ${pct}%; ${m.suppBonus > 0 ? 'background: linear-gradient(90deg, #8b5cf6, #00f0ff);' : ''}"></div>
        </div>
      `;
      gridEl.appendChild(item);
    });
  },

  renderMealsList() {
    const listEl = document.getElementById('meals-history-list');
    const suppListEl = document.getElementById('nutrition-supplements-list');

    if (listEl) {
      if (!this.meals || this.meals.length === 0) {
        listEl.innerHTML = `<div style="text-align:center; padding: 14px; font-size: 12px; color: var(--text-dim);">טרם נרשמו ארוחות היום. חפש מזון למעלה או השתמש בסריקת ברקוד/צילום AI!</div>`;
      } else {
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
      }
    }

    // Render Supplements in Nutrition View
    if (suppListEl) {
      if (!this.supplements || this.supplements.length === 0) {
        suppListEl.innerHTML = `
          <div style="padding:10px 14px; text-align:center; color:var(--text-dim); font-size:11.5px; background:rgba(255,255,255,0.02); border-radius:8px; border:1px dashed rgba(255,255,255,0.08);">
            💊 טרם נלקחו תוספים היום. תוספים שנרשמים מחשבים מיקרו-נוטריאנטים ומחזקים את ה-Vitality Matrix!
          </div>
        `;
      } else {
        const catIcons = {
          'vitamin': '🌿',
          'mineral': '🌙',
          'omega': '🐟',
          'performance': '⚡'
        };

        suppListEl.innerHTML = this.supplements.map(item => `
          <div class="meal-entry supp-overview-entry" style="border-right-color:#c084fc; background:rgba(147, 51, 234, 0.08);">
            <div class="meal-entry-info">
              <div class="meal-entry-name" style="color:#e9d5ff;">
                <span>${catIcons[item.category] || '🧪'}</span>
                <strong>${item.name}</strong>
                <span style="font-size:10px; color:#a855f7; font-family:var(--font-mono);">${item.dosage} • ${item.timestamp || ''}</span>
              </div>
              <div class="meal-entry-macros" style="color:#c084fc; font-size:10.5px;">
                ✓ חושב ב-Vitality Matrix • נותן EXP לאלכימיה ותובנות בריאות
              </div>
            </div>
            <button class="meal-delete-btn" onclick="AppState.deleteSupplement(${item.id})" title="מחק תוסף">✕</button>
          </div>
        `).join('');
      }
    }
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

  async addWater(amount, bevType = 'water', bevName = 'מים', bevIcon = '💧', caffeineMg = 0) {
    sfx.playPotion();
    try {
      const res = await fetch('/api/nutrition/water', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount_ml: amount,
          beverage_type: bevType,
          beverage_name: bevName,
          beverage_icon: bevIcon,
          caffeine_mg: caffeineMg
        })
      });
      const data = await res.json();
      if (data.leveling && data.leveling.leveled_up) {
        this.showLevelUpModal(data.leveling);
      }
      const addedMl = data.added_ml || amount;
      const caffText = caffeineMg > 0 ? ` (+${caffeineMg}mg קפאין)` : '';
      this.showToast(`${bevIcon} נוספו ${addedMl} מ״ל הידרציה מ${bevName}${caffText}!`);
      await this.fetchTodayData();
      if (typeof this.fetchDailyDebrief === 'function') this.fetchDailyDebrief();
    } catch (e) {
      console.warn('Network issue while logging water/beverage, queuing offline:', e);
      this.queueOfflineAction('/api/nutrition/water', 'POST', {
        amount_ml: amount,
        beverage_type: bevType,
        beverage_name: bevName,
        beverage_icon: bevIcon,
        caffeine_mg: caffeineMg
      }, `${amount}ml ${bevName}`);
      if (this.consumed) {
        this.consumed.water_ml = (this.consumed.water_ml || 0) + amount;
      }
      this.updateGauges();
      this.showToast(`${bevIcon} נוספו ${amount} מ״ל ${bevName} (נשמר מקומית)!`);
    }
  },

  addBeverage(bevType, amount, bevName, bevIcon, caffeineMg = 0) {
    this.addWater(amount, bevType, bevName, bevIcon, caffeineMg);
  },

  addCustomWater() {
    const inp = document.getElementById('custom-water-input');
    const select = document.getElementById('custom-water-type');
    const val = parseInt(inp ? inp.value : 0);
    if (val > 0) {
      let bevType = 'water';
      let bevName = 'מים';
      let bevIcon = '💧';
      let caffeineMg = 0;
      if (select) {
        const opt = select.options[select.selectedIndex];
        bevType = select.value || 'water';
        bevName = opt ? (opt.getAttribute('data-name') || 'מים') : 'מים';
        bevIcon = opt ? (opt.getAttribute('data-icon') || '💧') : '💧';
        caffeineMg = opt ? (parseInt(opt.getAttribute('data-caffeine') || '0') || 0) : 0;
      }
      this.addWater(val, bevType, bevName, bevIcon, caffeineMg);
      if (inp) inp.value = '';
    } else {
      alert('אנא הזן כמות תקינה (במ״ל)');
    }
  },

  async undoWater() {
    sfx.playClick();
    try {
      const res = await fetch('/api/nutrition/water', { method: 'DELETE' });
      if (res.ok) {
        this.showToast('↩️ הרישום האחרון בוטל בהצלחה');
        await this.fetchTodayData();
        if (typeof this.fetchDailyDebrief === 'function') this.fetchDailyDebrief();
      }
    } catch (e) {
      console.error('Undo water error:', e);
    }
  },

  async deleteWaterLog(id) {
    if (!confirm('האם למחוק רישום מים זה?')) return;
    sfx.playClick();
    try {
      const res = await fetch(`/api/nutrition/water/${id}`, { method: 'DELETE' });
      if (res.ok) {
        this.showToast('✕ רישום מים נמחק');
        await this.fetchTodayData();
        if (typeof this.fetchDailyDebrief === 'function') this.fetchDailyDebrief();
      }
    } catch (e) {
      console.error('Delete water log error:', e);
    }
  },

  toggleWaterHistory() {
    const el = document.getElementById('water-history-details');
    if (!el) return;
    const isHidden = el.style.display === 'none' || !el.style.display;
    el.style.display = isHidden ? 'block' : 'none';
    const btn = document.getElementById('toggle-water-history-btn');
    if (btn) {
      const count = this.waterLogs ? this.waterLogs.length : 0;
      btn.innerHTML = isHidden
        ? `📜 הסתר היסטוריית לגימות (${count})`
        : `📜 הצג היסטוריית לגימות היום (<span id="water-logs-count">${count}</span>)`;
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
      console.warn('Network issue while logging food, queuing offline:', e);
      // Optimistic offline queueing
      this.queueOfflineAction('/api/nutrition/log', 'POST', payload, payload.food_name || 'ארוחה');
      
      // Optimistic UI update
      if (!this.meals) this.meals = [];
      this.meals.unshift({
        id: 'off_' + Date.now(),
        food_name: payload.food_name,
        amount_grams: payload.amount_grams,
        calories: payload.calories,
        protein: payload.protein,
        carbs: payload.carbs,
        fats: payload.fats,
        time: new Date().toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
        offline: true
      });
      if (this.consumed) {
        this.consumed.calories = (this.consumed.calories || 0) + payload.calories;
        this.consumed.protein = (this.consumed.protein || 0) + payload.protein;
        this.consumed.carbs = (this.consumed.carbs || 0) + payload.carbs;
        this.consumed.fats = (this.consumed.fats || 0) + payload.fats;
      }
      this.renderMealsList();
      this.updateGauges();

      this.selectedFood = null;
      const sc = document.getElementById('staging-card');
      if (sc) sc.style.display = 'none';
      const fi = document.getElementById('food-search-input');
      if (fi) fi.value = '';
      sfx.playSystemNotification();
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

      // Multi-token search: ALL space-separated tokens must match in name_he or name
      const tokens = val.split(/\s+/).filter(t => t.length > 0);
      const matches = this.foodCatalog.filter(f => {
        const haystack = ((f.name_he || '') + ' ' + (f.name || '')).toLowerCase();
        return tokens.every(tok => haystack.includes(tok));
      });

      if (matches.length === 0) {
        resultsContainer.innerHTML = `<div style="padding:10px; font-size:12px; color:var(--text-dim);">לא נמצאו תוצאות. תוכל להוסיף מזון מותאם בהגדרות.</div>`;
      } else {
        resultsContainer.innerHTML = '';
        matches.slice(0, 20).forEach(item => {
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
  updateAwakeningPreview(keepCustom = false) {
    if (!keepCustom) {
      this.customAIGoals = null;
      const resBox = document.getElementById('ai-goal-result-box');
      if (resBox) resBox.style.display = 'none';
    }

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

  async calculateGoalsWithAI() {
    const inputEl = document.getElementById('ai-goal-input');
    const text = inputEl ? inputEl.value.trim() : '';
    if (!text) {
      alert('אנא תאר במילים שלך מה אתה רוצה להשיג (למשל: חיטוב לקראת הקיץ, עלייה נקייה במסה, שמירה על שריר ועבודה בלילות וכו\')');
      return;
    }
    sfx.playClick();
    const btn = document.getElementById('ai-calc-goals-btn');
    const origHtml = btn ? btn.innerHTML : '';
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span>⚡ מנתח פיזיולוגיה ויוצר תוכנית AI...</span>';
    }

    try {
      const weight = parseFloat(document.getElementById('awakening-weight').value) || (this.profile ? this.profile.weight : 78);
      const height = parseFloat(document.getElementById('awakening-height').value) || (this.profile ? this.profile.height : 178);
      const age = parseInt(document.getElementById('awakening-age').value) || (this.profile ? this.profile.age : 25);
      const sex = document.getElementById('awakening-sex').value || (this.profile ? this.profile.sex : 'male');
      const activity = document.getElementById('awakening-activity').value || (this.profile ? this.profile.activity_level : 'moderate');

      const res = await fetch('/api/goals/ai-calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goal_text: text,
          weight,
          height,
          age,
          sex,
          activity_level: activity
        })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      this.customAIGoals = data;

      // Update the awakening preview fields
      const cals = data.target_calories;
      const p = data.target_protein;
      const c = data.target_carbs;
      const f = data.target_fats;
      const w = data.target_water;

      const prevCals = document.getElementById('prev-target-cals');
      if (prevCals) prevCals.innerText = `${cals} kcal`;
      const prevP = document.getElementById('prev-protein');
      if (prevP) prevP.innerText = `${p}g (${Math.round((p * 4 / cals) * 100)}%)`;
      const prevC = document.getElementById('prev-carbs');
      if (prevC) prevC.innerText = `${c}g (${Math.round((c * 4 / cals) * 100)}%)`;
      const prevF = document.getElementById('prev-fats');
      if (prevF) prevF.innerText = `${f}g (${Math.round((f * 9 / cals) * 100)}%)`;
      const prevW = document.getElementById('prev-water');
      if (prevW) prevW.innerText = `${w} ml`;

      // Also sync path dropdown if applicable
      const goalSelect = document.getElementById('awakening-goal');
      if (goalSelect && data.goal_type) {
        goalSelect.value = data.goal_type;
      }

      // Render the AI explanation box
      const resultBox = document.getElementById('ai-goal-result-box');
      const headlineEl = document.getElementById('ai-result-headline');
      const expEl = document.getElementById('ai-result-explanation');
      const tipEl = document.getElementById('ai-result-tip');

      if (resultBox) resultBox.style.display = 'block';
      if (headlineEl) headlineEl.innerText = `🎯 ${data.analysis_headline || 'יעדים מותאמים אישית'}`;
      if (expEl) expEl.innerText = data.ai_explanation || '';
      if (tipEl) {
        tipEl.innerText = `💡 טיפ צייד מדעי: ${data.hunter_rank_tip || 'הקפד על עקביות יומית כדי למקסם תוצאות.'}`;
        tipEl.style.display = 'block';
      }

      this.showToast('✨ היעדים חושבו בהצלחה לפי המטרה שלך!');
    } catch (err) {
      console.error('AI Goal calculation error:', err);
      alert('שגיאה בחישוב היעדים: ' + err.message);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = origHtml;
      }
    }
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

    if (this.customAIGoals) {
      payload.target_calories = this.customAIGoals.target_calories;
      payload.target_protein = this.customAIGoals.target_protein;
      payload.target_carbs = this.customAIGoals.target_carbs;
      payload.target_fats = this.customAIGoals.target_fats;
      payload.target_water = this.customAIGoals.target_water;
      payload.target_fiber = this.customAIGoals.target_fiber;
    }

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

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  },

  // First-Time Awakening Onboarding Logic
  checkFirstTimeAwakening() {
    const isLocalAwakened = localStorage.getItem('hunter_awakened') === 'true';
    const isAwakenedInDB = this.profile && (this.profile.is_awakened === 1 || this.profile.is_awakened === true);

    // If either localStorage or DB says awakened, the hunter is ALREADY awakened!
    if (isLocalAwakened || isAwakenedInDB) {
      if (!isLocalAwakened) {
        localStorage.setItem('hunter_awakened', 'true');
      }
      if (!isAwakenedInDB) {
        // Asynchronously synchronize DB state so it doesn't stay 0
        fetch('/api/profile', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_awakened: 1 })
        }).catch(err => console.warn('Sync is_awakened error:', err));
      }
      return;
    }

    // Only if NEVER awakened locally and NEVER in DB:
    setTimeout(() => {
      this.openFirstTimeAwakening(false);
    }, 400);
  },

  openFirstTimeAwakening(force = false) {
    sfx.playClick();
    const overlay = document.getElementById('first-time-awakening-overlay');
    if (!overlay) return;

    const p = this.profile || {};
    const nameEl = document.getElementById('init-name');
    if (nameEl) nameEl.value = p.name || 'צייד רום';

    const ageEl = document.getElementById('init-age');
    if (ageEl) ageEl.value = p.age || 26;

    const sexEl = document.getElementById('init-sex');
    if (sexEl) sexEl.value = p.sex || 'male';

    const heightEl = document.getElementById('init-height');
    if (heightEl) heightEl.value = p.height || 180;

    const weightEl = document.getElementById('init-weight');
    if (weightEl) weightEl.value = p.weight || 80;

    const targetWeightEl = document.getElementById('init-target-weight');
    if (targetWeightEl) targetWeightEl.value = p.target_weight || 75;

    const shiftModeEl = document.getElementById('init-shift-mode');
    if (shiftModeEl) shiftModeEl.value = p.shift_mode || 'standard';

    const actEl = document.getElementById('init-activity');
    if (actEl) actEl.value = p.activity_level || 'moderate';

    const goalPathEl = document.getElementById('init-goal-path');
    if (goalPathEl) goalPathEl.value = p.goal || 'cut';

    if (p.goal_custom_text) {
      this.lastAwakeningGoalText = p.goal_custom_text;
    }

    this.updateOnboardingPreview(true);

    overlay.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Auto-scroll chat stream to bottom and focus input
    setTimeout(() => {
      const stream = document.getElementById('awakening-chat-stream');
      if (stream) stream.scrollTop = stream.scrollHeight;
      const input = document.getElementById('awakening-chat-input');
      if (input) input.focus();
    }, 150);
  },

  closeFirstTimeAwakening() {
    localStorage.setItem('hunter_awakened', 'true');
    const overlay = document.getElementById('first-time-awakening-overlay');
    if (overlay) overlay.style.display = 'none';
    document.body.style.overflow = '';
  },

  skipFirstTimeAwakening() {
    sfx.playClick();
    localStorage.setItem('hunter_awakened', 'true');
    fetch('/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_awakened: 1 })
    }).catch(err => console.warn('Sync is_awakened error:', err));
    this.closeFirstTimeAwakening();
    this.showToast('ℹ️ המשכת עם הגדרות ברירת מחדל. תוכל לערוך יעדים ולהתייעץ עם ה-AI בכל שלב.');
  },

  setAwakeningChatPrompt(text) {
    const input = document.getElementById('awakening-chat-input');
    if (input) {
      input.value = text;
      input.focus();
      input.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  },

  updateOnboardingPreview(keepCustom = false) {
    if (!keepCustom) {
      this.customAIGoals = null;
    }

    const weight = parseFloat(document.getElementById('init-weight')?.value) || 80;
    const height = parseFloat(document.getElementById('init-height')?.value) || 180;
    const age = parseInt(document.getElementById('init-age')?.value) || 26;
    const sex = document.getElementById('init-sex')?.value || 'male';
    const activity = document.getElementById('init-activity')?.value || 'moderate';
    const goal = document.getElementById('init-goal-path')?.value || 'cut';

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
    const fiber = Math.max(28, Math.round((cals / 1000) * 14));

    const bmrEl = document.getElementById('init-prev-bmr');
    if (bmrEl) bmrEl.innerText = `${Math.round(bmr).toLocaleString()} kcal`;

    const tdeeEl = document.getElementById('init-prev-tdee');
    if (tdeeEl) tdeeEl.innerText = `${tdee.toLocaleString()} kcal`;

    const calsEl = document.getElementById('init-prev-cals');
    if (calsEl) calsEl.innerText = `${cals.toLocaleString()} kcal`;

    const protEl = document.getElementById('init-prev-prot');
    if (protEl) protEl.innerText = `${protein}g (${Math.round((protein * 4 / cals) * 100)}%)`;

    const carbsEl = document.getElementById('init-prev-carbs');
    if (carbsEl) carbsEl.innerText = `${carbs}g (${Math.round((carbs * 4 / cals) * 100)}%)`;

    const fatsEl = document.getElementById('init-prev-fats');
    if (fatsEl) fatsEl.innerText = `${fats}g (${Math.round((fats * 9 / cals) * 100)}%)`;

    const waterEl = document.getElementById('init-prev-water');
    if (waterEl) waterEl.innerText = `${water.toLocaleString()} ml`;

    const fiberEl = document.getElementById('init-prev-fiber');
    if (fiberEl) fiberEl.innerText = `${fiber}g`;

    // Dynamic target weight alignment based on goal
    const targetWeightEl = document.getElementById('init-target-weight');
    if (targetWeightEl) {
      const tw = parseFloat(targetWeightEl.value);
      if (goal === 'bulk') {
        if (!tw || tw <= weight) {
          targetWeightEl.value = Math.round((weight + 4.0) * 10) / 10;
        }
      } else if (goal === 'cut') {
        if (!tw || tw >= weight) {
          targetWeightEl.value = Math.round(Math.max(40.0, weight - 4.0) * 10) / 10;
        }
      } else if (goal === 'maintain') {
        if (!tw) {
          targetWeightEl.value = Math.round(weight * 10) / 10;
        }
      }
    }
  },

  async sendAwakeningChat() {
    const input = document.getElementById('awakening-chat-input');
    const text = input ? input.value.trim() : '';
    if (!text) {
      if (input) input.focus();
      return;
    }

    sfx.playClick();
    const stream = document.getElementById('awakening-chat-stream');
    const sendBtn = document.getElementById('awakening-chat-send-btn');
    if (sendBtn) sendBtn.disabled = true;

    // Time tag
    const now = new Date();
    const timeStr = now.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' });

    // 1. Append user message bubble
    if (stream) {
      const userBubble = document.createElement('div');
      userBubble.className = 'chat-bubble user-msg';
      userBubble.innerHTML = `
        <div class="chat-msg-header">
          <span class="chat-sender-name">👤 הצייד</span>
          <span class="chat-time-tag">${timeStr}</span>
        </div>
        <div class="chat-msg-body">${this.escapeHtml(text)}</div>
      `;
      stream.appendChild(userBubble);
      stream.scrollTop = stream.scrollHeight;
    }

    // Clear input
    if (input) input.value = '';

    // 2. Append thinking bubble
    let thinkingBubble = null;
    if (stream) {
      thinkingBubble = document.createElement('div');
      thinkingBubble.className = 'chat-bubble ai-msg ai-thinking-bubble';
      thinkingBubble.id = 'ai-thinking-bubble';
      thinkingBubble.innerHTML = `
        <div class="chat-msg-header">
          <span class="chat-sender-name">⚡ SYSTEM AI</span>
          <span class="chat-time-tag">מנתח ומחשב...</span>
        </div>
        <div class="chat-msg-body">
          <span class="thinking-spinner">⚡</span> המערכת מנתחת את היעדים והנתונים הפיזיולוגיים ב-AI...
        </div>
      `;
      stream.appendChild(thinkingBubble);
      stream.scrollTop = stream.scrollHeight;
    }

    // 3. Collect current manual form values
    const weight = parseFloat(document.getElementById('init-weight')?.value) || 80;
    const height = parseFloat(document.getElementById('init-height')?.value) || 180;
    const age = parseInt(document.getElementById('init-age')?.value) || 26;
    const sex = document.getElementById('init-sex')?.value || 'male';
    const activity = document.getElementById('init-activity')?.value || 'moderate';

    try {
      const res = await fetch('/api/goals/ai-calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          goal_text: text,
          weight,
          height,
          age,
          sex,
          activity_level: activity
        })
      });

      const data = await res.json();
      if (data.error) throw new Error(data.error);

      // Save custom goals and last goal text
      this.customAIGoals = data;
      this.lastAwakeningGoalText = text;

      // Auto-update biometrics if detected in user text
      if (data.detected_weight) {
        const wEl = document.getElementById('init-weight');
        if (wEl) wEl.value = data.detected_weight;
      }
      if (data.detected_height) {
        const hEl = document.getElementById('init-height');
        if (hEl) hEl.value = data.detected_height;
      }
      if (data.detected_age) {
        const aEl = document.getElementById('init-age');
        if (aEl) aEl.value = data.detected_age;
      }
      if (data.detected_target_weight) {
        const twEl = document.getElementById('init-target-weight');
        if (twEl) twEl.value = data.detected_target_weight;
      }
      if (data.goal_type) {
        const gpEl = document.getElementById('init-goal-path');
        if (gpEl) gpEl.value = data.goal_type;
      }

      // Update blueprint summary chips in overlay
      const cals = data.target_calories;
      const p = data.target_protein;
      const c = data.target_carbs;
      const f = data.target_fats;
      const w = data.target_water;
      const fib = data.target_fiber || 30;

      const calsEl = document.getElementById('init-prev-cals');
      if (calsEl) calsEl.innerText = `${cals.toLocaleString()} kcal`;

      const protEl = document.getElementById('init-prev-prot');
      if (protEl) protEl.innerText = `${p}g (${Math.round((p * 4 / cals) * 100)}%)`;

      const carbsEl = document.getElementById('init-prev-carbs');
      if (carbsEl) carbsEl.innerText = `${c}g (${Math.round((c * 4 / cals) * 100)}%)`;

      const fatsEl = document.getElementById('init-prev-fats');
      if (fatsEl) fatsEl.innerText = `${f}g (${Math.round((f * 9 / cals) * 100)}%)`;

      const waterEl = document.getElementById('init-prev-water');
      if (waterEl) waterEl.innerText = `${w.toLocaleString()} ml`;

      const fibEl = document.getElementById('init-prev-fiber');
      if (fibEl) fibEl.innerText = `${fib}g`;

      // Remove thinking bubble
      if (thinkingBubble && thinkingBubble.parentNode) {
        thinkingBubble.parentNode.removeChild(thinkingBubble);
      }

      // Append rich AI response bubble
      if (stream) {
        const aiBubble = document.createElement('div');
        aiBubble.className = 'chat-bubble ai-msg';
        aiBubble.innerHTML = `
          <div class="chat-msg-header">
            <span class="chat-sender-name">⚡ SYSTEM AI</span>
            <span class="chat-time-tag">${timeStr}</span>
          </div>
          <div class="chat-msg-body">
            <div class="ai-msg-headline">🎯 ${this.escapeHtml(data.analysis_headline || 'מפרט מדעי מותאם אישית')}</div>
            <div class="ai-msg-text">${this.escapeHtml(data.ai_explanation || '')}</div>
            
            <div class="ai-chat-blueprint">
              <div class="ai-cb-item"><span class="ai-cb-k">🔥 יעד קלוריות:</span> <strong class="ai-cb-v cals-glow">${data.target_calories.toLocaleString()} kcal</strong></div>
              <div class="ai-cb-item"><span class="ai-cb-k">🥩 יעד חלבון:</span> <strong class="ai-cb-v prot-glow">${data.target_protein}g</strong></div>
              <div class="ai-cb-item"><span class="ai-cb-k">🍞 פחמימות:</span> <strong class="ai-cb-v">${data.target_carbs}g</strong></div>
              <div class="ai-cb-item"><span class="ai-cb-k">🥑 שומנים:</span> <strong class="ai-cb-v">${data.target_fats}g</strong></div>
              <div class="ai-cb-item"><span class="ai-cb-k">💧 מים יומי:</span> <strong class="ai-cb-v water-glow">${data.target_water.toLocaleString()} ml</strong></div>
              <div class="ai-cb-item"><span class="ai-cb-k">🌾 סיבים:</span> <strong class="ai-cb-v">${data.target_fiber || 30}g</strong></div>
            </div>

            ${data.hunter_rank_tip ? `<div class="ai-chat-tip">💡 <strong>המלצת המערכת:</strong> ${this.escapeHtml(data.hunter_rank_tip)}</div>` : ''}
          </div>
        `;
        stream.appendChild(aiBubble);
        stream.scrollTop = stream.scrollHeight;
      }

      sfx.playLevelUp();
      this.showToast('✨ היעדים והמפרט חושבו בהצלחה לפי המטרה שלך!');
    } catch (err) {
      console.error('sendAwakeningChat error:', err);
      if (thinkingBubble && thinkingBubble.parentNode) {
        thinkingBubble.parentNode.removeChild(thinkingBubble);
      }
      if (stream) {
        const errBubble = document.createElement('div');
        errBubble.className = 'chat-bubble ai-msg';
        errBubble.style.borderColor = '#ef4444';
        errBubble.innerHTML = `
          <div class="chat-msg-header">
            <span class="chat-sender-name" style="color:#f87171;">⚠️ SYSTEM ERROR</span>
            <span class="chat-time-tag">${timeStr}</span>
          </div>
          <div class="chat-msg-body" style="color:#fca5a5;">
            אירעה שגיאה בעיבוד היעד: ${this.escapeHtml(err.message)}.<br>
            נסה לנסח מחדש או לבדוק את הנתונים.
          </div>
        `;
        stream.appendChild(errBubble);
        stream.scrollTop = stream.scrollHeight;
      }
    } finally {
      if (sendBtn) sendBtn.disabled = false;
    }
  },

  // Legacy fallback for backward compatibility
  async calcOnboardingWithAI() {
    return this.sendAwakeningChat();
  },

  async submitFirstTimeAwakening() {
    sfx.playClick();
    const name = document.getElementById('init-name')?.value || 'צייד רום';
    const weight = parseFloat(document.getElementById('init-weight')?.value) || 80;
    const height = parseFloat(document.getElementById('init-height')?.value) || 180;
    const goal = document.getElementById('init-goal-path')?.value || 'cut';

    let targetWeight = parseFloat(document.getElementById('init-target-weight')?.value);
    if (goal === 'bulk') {
      if (!targetWeight || targetWeight <= weight) {
        targetWeight = Math.round((weight + 4.0) * 10) / 10;
      }
    } else if (goal === 'cut') {
      if (!targetWeight || targetWeight >= weight) {
        targetWeight = Math.round(Math.max(40.0, weight - 4.0) * 10) / 10;
      }
    } else {
      if (!targetWeight) targetWeight = weight;
    }

    const age = parseInt(document.getElementById('init-age')?.value) || 26;
    const sex = document.getElementById('init-sex')?.value || 'male';
    const activity = document.getElementById('init-activity')?.value || 'moderate';
    const shiftMode = document.getElementById('init-shift-mode')?.value || 'standard';
    const goalText = this.lastAwakeningGoalText || document.getElementById('awakening-chat-input')?.value || '';

    const payload = {
      name,
      weight,
      height,
      target_weight: targetWeight,
      age,
      sex,
      activity_level: activity,
      goal,
      shift_mode: shiftMode,
      goal_custom_text: goalText
    };

    if (this.customAIGoals) {
      payload.target_calories = this.customAIGoals.target_calories;
      payload.target_protein = this.customAIGoals.target_protein;
      payload.target_carbs = this.customAIGoals.target_carbs;
      payload.target_fats = this.customAIGoals.target_fats;
      payload.target_water = this.customAIGoals.target_water;
      payload.target_fiber = this.customAIGoals.target_fiber;
      payload.ai_analysis_headline = this.customAIGoals.analysis_headline || '';
      payload.ai_explanation = this.customAIGoals.ai_explanation || '';
      payload.ai_hunter_tip = this.customAIGoals.hunter_rank_tip || '';
    }

    const btn = document.getElementById('submit-onboarding-btn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span>⏳ מעדכן נתונים ומתעורר...</span>';
    }

    try {
      const res = await fetch('/api/awakening', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      localStorage.setItem('hunter_awakened', 'true');
      this.closeFirstTimeAwakening();

      sfx.playLevelUp();
      this.showToast('⚔️ טקס ההתעוררות הושלם בהצלחה! ברוך הבא לצייד.');

      if (data.leveling && data.leveling.leveled_up) {
        this.showLevelUpModal(data.leveling);
      }
      if (data.newly_unlocked_achievements && data.newly_unlocked_achievements.length > 0) {
        this.checkNewlyUnlocked(data.newly_unlocked_achievements);
      }
      await this.fetchTodayData();
      if (typeof this.fetchDailyDebrief === 'function') this.fetchDailyDebrief();
    } catch (err) {
      console.error('Awakening submit error:', err);
      alert('שגיאה בשמירת נתוני ההתעוררות: ' + err.message);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<span class="cta-rune">⚔️</span><span class="cta-text">אשר התעוררות והיכנס למערכת (AWAKEN NOW)</span>';
      }
    }
  },

  async resetAwakeningForTesting() {
    if (!confirm('האם לאפס את סטטוס ההתעוררות כדי לצפות שוב במסך הפתיחה?')) return;
    try {
      localStorage.removeItem('hunter_awakened');
      await fetch('/api/awakening/reset', { method: 'POST' });
      await this.fetchTodayData();
      this.openFirstTimeAwakening(true);
    } catch (e) {
      console.error(e);
    }
  },

  // ========================================================
  // INTERACTIVE AI CONSULTATION & ACTIVE RECOMMENDATIONS
  // ========================================================
  pendingTargetsMap: {},

  async openAIConsultationModal(initialPrompt = '') {
    sfx.playClick();
    const modal = document.getElementById('ai-consultation-modal');
    if (!modal) return;

    // Update live hunter status strip inside the modal
    const p = this.profile || {};
    const hEl = document.getElementById('consult-hunter-height');
    if (hEl) hEl.innerText = p.height || '180';
    const wEl = document.getElementById('consult-hunter-weight');
    if (wEl) wEl.innerText = p.weight ? Number(p.weight).toFixed(1) : '83.0';
    const twEl = document.getElementById('consult-hunter-target');
    if (twEl) twEl.innerText = p.target_weight ? Number(p.target_weight).toFixed(1) : '87.0';
    const gEl = document.getElementById('consult-hunter-goal');
    if (gEl) {
      const gMap = { bulk: 'מסה נקייה', cut: 'חיטוב ושריפת שומן', maintain: 'שמירה ואיזון' };
      gEl.innerText = gMap[p.goal] || p.goal || 'מסה נקייה';
    }
    const cEl = document.getElementById('consult-hunter-cals');
    if (cEl) cEl.innerText = p.target_calories ? p.target_calories.toLocaleString() : '2,550';
    const protEl = document.getElementById('consult-hunter-prot');
    if (protEl) protEl.innerText = p.target_protein || '175';
    const watEl = document.getElementById('consult-hunter-water');
    if (watEl) watEl.innerText = p.target_water ? p.target_water.toLocaleString() : '3,300';

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Load consultation history
    await this.loadAIConsultationHistory();

    const stream = document.getElementById('ai-consult-stream');
    if (stream) {
      setTimeout(() => { stream.scrollTop = stream.scrollHeight; }, 100);
    }

    const input = document.getElementById('ai-consult-input');
    if (input) {
      if (initialPrompt) input.value = initialPrompt;
      setTimeout(() => input.focus(), 150);
    }
  },

  closeAIConsultationModal() {
    const modal = document.getElementById('ai-consultation-modal');
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
  },

  setAIConsultPrompt(text) {
    const input = document.getElementById('ai-consult-input');
    if (input) {
      input.value = text;
      input.focus();
    }
  },

  async loadAIConsultationHistory() {
    try {
      const res = await fetch('/api/ai/consult/history');
      if (res.ok) {
        const data = await res.json();
        this.aiConsultHistory = data.messages || [];
        this.renderAIConsultStream();
      }
    } catch (err) {
      console.warn('Failed to load consultation history:', err);
    }
  },

  renderAIConsultStream() {
    const stream = document.getElementById('ai-consult-stream');
    if (!stream) return;
    this.pendingTargetsMap = {};

    if (!this.aiConsultHistory || this.aiConsultHistory.length === 0) {
      stream.innerHTML = `
        <div class="chat-bubble ai-msg">
          <div class="chat-msg-header">
            <span class="chat-sender-name">⚡ SYSTEM AI ADVISOR</span>
            <span class="chat-time-tag">הודעת מערכת</span>
          </div>
          <div class="chat-msg-body">
            שלום צייד! אני יועץ המערכת שלך בזמן אמת.<br>
            יש לך שאלות על עלייה במסה, חלוקת 175 גרם חלבון ביום, תוספי תזונה (קריאטין 5 גרם, מגנזיום, אומגה 3), התמודדות עם חוסר תיאבון תחת אטנט (Attent), משמרות לילה, או חישוב מחדש של היעדים?<br><br>
            <strong>שאל אותי בחופשיות או בחר באחת מההצעות למטה!</strong>
          </div>
        </div>
      `;
      return;
    }

    stream.innerHTML = this.aiConsultHistory.map(msg => {
      const isUser = msg.sender === 'user';
      const timeStr = msg.created_at ? new Date(msg.created_at).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }) : '';
      let recsHtml = '';
      if (msg.recommendations && msg.recommendations.length > 0) {
        recsHtml = `
          <div class="ai-consult-recs-wrap">
            <div class="ai-consult-recs-title">📋 המלצות פעולה שנשמרו במערכת:</div>
            ${msg.recommendations.map(r => `
              <div class="ai-consult-rec-chip">
                <span class="rec-chip-cat">[${this.escapeHtml(r.category || 'מערכת')}]</span>
                <strong>${this.escapeHtml(r.title || '')}</strong>: ${this.escapeHtml(r.content || '')}
              </div>
            `).join('')}
          </div>
        `;
      }

      let applyTargetsHtml = '';
      if (msg.suggested_targets && (msg.suggested_targets.calories || msg.suggested_targets.protein)) {
        const t = msg.suggested_targets;
        this.pendingTargetsMap[msg.id] = t;
        applyTargetsHtml = `
          <div class="ai-suggested-targets-card">
            <div class="astc-title">🎯 הצעת עדכון יעדים מהיועץ:</div>
            <div class="astc-grid">
              ${t.calories ? `<span>🔥 קלוריות: <strong>${t.calories.toLocaleString()} kcal</strong></span>` : ''}
              ${t.protein ? `<span>🥩 חלבון: <strong>${t.protein}g</strong></span>` : ''}
              ${t.target_weight ? `<span>⚖️ משקל יעד: <strong>${t.target_weight} kg</strong></span>` : ''}
              ${t.water ? `<span>💧 מים: <strong>${t.water.toLocaleString()} ml</strong></span>` : ''}
            </div>
            <button type="button" class="ai-apply-targets-btn" onclick="AppState.applyAIConsultTargetsById(${msg.id})">
              ⚡ החל יעדים אלו כעת על הפרופיל
            </button>
          </div>
        `;
      }

      return `
        <div class="chat-bubble ${isUser ? 'user-msg' : 'ai-msg'}">
          <div class="chat-msg-header">
            <span class="chat-sender-name">${isUser ? '👤 הצייד' : '⚡ SYSTEM AI ADVISOR'}</span>
            <span class="chat-time-tag">${timeStr}</span>
          </div>
          <div class="chat-msg-body">
            ${this.escapeHtml(msg.message || '').replace(/\n/g, '<br>')}
            ${recsHtml}
            ${applyTargetsHtml}
          </div>
        </div>
      `;
    }).join('');

    stream.scrollTop = stream.scrollHeight;
  },

  async sendAIConsultation() {
    const input = document.getElementById('ai-consult-input');
    const text = input ? input.value.trim() : '';
    if (!text) {
      if (input) input.focus();
      return;
    }

    sfx.playClick();
    const sendBtn = document.getElementById('ai-consult-send-btn');
    if (sendBtn) sendBtn.disabled = true;

    const stream = document.getElementById('ai-consult-stream');
    const nowTime = new Date().toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' });

    // 1. Append user message bubble
    if (stream) {
      const userBubble = document.createElement('div');
      userBubble.className = 'chat-bubble user-msg';
      userBubble.innerHTML = `
        <div class="chat-msg-header">
          <span class="chat-sender-name">👤 הצייד</span>
          <span class="chat-time-tag">${nowTime}</span>
        </div>
        <div class="chat-msg-body">${this.escapeHtml(text)}</div>
      `;
      stream.appendChild(userBubble);
      stream.scrollTop = stream.scrollHeight;
    }

    if (input) input.value = '';

    // 2. Append thinking bubble
    let thinkingBubble = null;
    if (stream) {
      thinkingBubble = document.createElement('div');
      thinkingBubble.className = 'chat-bubble ai-msg ai-thinking-bubble';
      thinkingBubble.innerHTML = `
        <div class="chat-msg-header">
          <span class="chat-sender-name">⚡ SYSTEM AI</span>
          <span class="chat-time-tag">מנתח ומחשב ייעוץ...</span>
        </div>
        <div class="chat-msg-body">
          <span class="thinking-spinner">⚡</span> יועץ המערכת מחשב תשובה מותאמת אישית לנתוניך...
        </div>
      `;
      stream.appendChild(thinkingBubble);
      stream.scrollTop = stream.scrollHeight;
    }

    try {
      const res = await fetch('/api/ai/consult', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      if (thinkingBubble && thinkingBubble.parentNode) {
        thinkingBubble.parentNode.removeChild(thinkingBubble);
      }

      await this.loadAIConsultationHistory();
      await this.fetchAIRecommendations();
      sfx.playLevelUp();
    } catch (err) {
      console.error('AIConsult error:', err);
      if (thinkingBubble && thinkingBubble.parentNode) {
        thinkingBubble.parentNode.removeChild(thinkingBubble);
      }
      if (stream) {
        const errBubble = document.createElement('div');
        errBubble.className = 'chat-bubble ai-msg';
        errBubble.style.borderColor = '#ef4444';
        errBubble.innerHTML = `
          <div class="chat-msg-header">
            <span class="chat-sender-name" style="color:#ef4444;">⚠️ SYSTEM ERROR</span>
          </div>
          <div class="chat-msg-body" style="color:#fca5a5;">
            שגיאה בהתייעצות: ${this.escapeHtml(err.message)}
          </div>
        `;
        stream.appendChild(errBubble);
        stream.scrollTop = stream.scrollHeight;
      }
    } finally {
      if (sendBtn) sendBtn.disabled = false;
    }
  },

  applyAIConsultTargetsById(id) {
    const t = this.pendingTargetsMap[id];
    if (t) {
      this.applyAIConsultTargets(t);
    }
  },

  async applyAIConsultTargets(targets) {
    if (!targets) return;
    sfx.playClick();
    try {
      const res = await fetch('/api/ai/apply-targets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(targets)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Apply failed');

      if (data.profile) {
        this.profile = data.profile;
        localStorage.setItem('hunter_profile', JSON.stringify(data.profile));
      }
      sfx.playLevelUp();
      this.renderProfile();
      this.renderCalorieGauge();
      this.renderMacroBars();
      this.renderWaterCockpit();
      this.showToast('🎯 היעדים עודכנו בהצלחה ונשמרו במערכת!');
      this.saveLocalSnapshot();
    } catch (err) {
      alert('שגיאה בעדכון יעדים: ' + err.message);
    }
  },

  openQuickEditBiometrics(field = 'height') {
    sfx.playClick();
    this.currentQuickBioField = field;
    const modal = document.getElementById('quick-biometrics-modal');
    if (!modal) return;

    const titleEl = document.getElementById('quick-bio-modal-title');
    const labelEl = document.getElementById('quick-bio-input-label');
    const valInput = document.getElementById('quick-bio-input-val');
    const helpEl = document.getElementById('quick-bio-help-text');
    const p = this.profile || {};

    const configs = {
      height: {
        title: 'עדכון גובה (Height)',
        label: 'גובה בסנטימטרים (ס״מ)',
        val: p.height || 180,
        step: 1,
        help: 'עדכון הגובה מחושב מיד מחדש במשוואות BMR ו-TDEE לעדכון דיוק קלורי ומסת שריר.'
      },
      weight: {
        title: 'עדכון משקל נוכחי (Weight)',
        label: 'משקל נוכחי (ק״ג)',
        val: p.weight ? Number(p.weight).toFixed(1) : 83.0,
        step: 0.5,
        help: 'עדכון המשקל ישפיע מיידית על גרף ההתקדמות, קצב ההתקדמות ומשוואות חילוף החומרים.'
      },
      target_weight: {
        title: 'עדכון יעד משקל (Target Weight)',
        label: 'יעד משקל מבוקש (ק״ג)',
        val: p.target_weight ? Number(p.target_weight).toFixed(1) : 87.0,
        step: 0.5,
        help: 'משקל המטרה קובע את משך התוכנית ומסייע לאלגוריתם ה-AI לבנות גירעון או עודף קלורי מדויק.'
      },
      age: {
        title: 'עדכון גיל (Age)',
        label: 'גיל בשנים',
        val: p.age || 26,
        step: 1,
        help: 'גיל משמש כגורם מפתח לחישוב קצב שריפת שומנים וחילוף חומרים במנוחה.'
      }
    };

    const cfg = configs[field] || configs.height;
    if (titleEl) titleEl.innerText = cfg.title;
    if (labelEl) labelEl.innerText = cfg.label;
    if (valInput) {
      valInput.value = cfg.val;
      valInput.step = cfg.step || 1;
    }
    if (helpEl) helpEl.innerText = cfg.help;

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    setTimeout(() => {
      if (valInput) {
        valInput.focus();
        valInput.select();
      }
    }, 120);
  },

  closeQuickEditBiometrics() {
    const modal = document.getElementById('quick-biometrics-modal');
    if (modal) modal.style.display = 'none';
    document.body.style.overflow = '';
  },

  stepBioInput(delta) {
    sfx.playClick();
    const valInput = document.getElementById('quick-bio-input-val');
    if (!valInput) return;
    let curr = parseFloat(valInput.value) || 0;
    const step = parseFloat(valInput.step) || 1;
    curr += (delta * step);
    if (step < 1) {
      valInput.value = curr.toFixed(1);
    } else {
      valInput.value = Math.round(curr);
    }
  },

  async saveQuickEditBiometrics() {
    sfx.playClick();
    const valInput = document.getElementById('quick-bio-input-val');
    if (!valInput) return;
    const val = parseFloat(valInput.value);
    if (!val || val <= 0) {
      this.showToast('⚠️ נא להזין ערך תקין', 'error');
      return;
    }

    const field = this.currentQuickBioField || 'height';
    const payload = {};
    payload[field] = val;

    try {
      this.showToast('⚡ מעדכן מדדים ומחשב BMR/TDEE מחדש...', 'info');
      const res = await fetch('/api/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const updated = await res.json();
        this.profile = { ...this.profile, ...updated, ...payload };
        localStorage.setItem('hunter_profile', JSON.stringify(this.profile));

        this.renderProfile();
        if (typeof this.renderCalorieGauge === 'function') this.renderCalorieGauge();
        if (typeof this.renderMacroBars === 'function') this.renderMacroBars();
        if (typeof this.renderWaterCockpit === 'function') this.renderWaterCockpit();
        this.saveLocalSnapshot();

        this.closeQuickEditBiometrics();
        sfx.playLevelUp();
        const fieldHebrew = {
          height: `גובה עודכן ל-${val} ס״מ`,
          weight: `משקל עודכן ל-${val} ק״ג`,
          target_weight: `יעד משקל עודכן ל-${val} ק״ג`,
          age: `גיל עודכן ל-${val}`
        }[field] || 'המדד עודכן בהצלחה!';
        this.showToast(`✅ ${fieldHebrew} ונשמר במערכת!`, 'success');
      } else {
        this.showToast('❌ שגיאה בעדכון הנתונים', 'error');
      }
    } catch (e) {
      console.error('Error saving biometrics:', e);
      this.showToast('❌ שגיאת תקשורת עם המערכת', 'error');
    }
  },

  async fetchAIRecommendations() {
    try {
      const res = await fetch('/api/ai/recommendations');
      if (res.ok) {
        const data = await res.json();
        this.aiRecommendations = data.recommendations || [];
        this.renderAIRecommendations();
      }
    } catch (err) {
      console.warn('Failed to fetch recommendations:', err);
    }
  },

  renderAIRecommendations() {
    const profileCont = document.getElementById('profile-ai-recs-container');
    const nutCont = document.getElementById('nutrition-ai-recs-container');
    const recs = this.aiRecommendations || [];

    const categoryIcons = {
      bulk: '💪',
      protein: '🥩',
      supplements: '💊',
      attent: '🧠',
      night_shift: '🌙',
      hydration: '💧',
      recovery: '🛌',
      nutrition: '🥗'
    };

    const buildHtml = (limit = null) => {
      const list = limit ? recs.slice(0, limit) : recs;
      if (list.length === 0) {
        return `
          <div class="ai-rec-empty">
            <span>💡</span>
            <div>אין עדיין המלצות שמורות במערכת. פתח את יועץ ה-AI לקבלת המלצות מותאמות אישית!</div>
            <button type="button" class="ai-rec-consult-now-btn" onclick="AppState.openAIConsultationModal()">💬 פתח יועץ AI</button>
          </div>
        `;
      }

      return `
        <div class="ai-recs-cards-list">
          ${list.map(r => {
            const icon = categoryIcons[r.category] || '⚡';
            return `
              <div class="ai-rec-item-card ${r.is_active ? 'active' : 'completed'}">
                <div class="ai-rec-item-header">
                  <div class="ai-rec-title-group">
                    <span class="ai-rec-icon">${icon}</span>
                    <strong class="ai-rec-title">${this.escapeHtml(r.title)}</strong>
                    <span class="ai-rec-category-tag">[${this.escapeHtml(r.category)}]</span>
                  </div>
                  <div class="ai-rec-actions">
                    <button type="button" class="ai-rec-toggle-btn" onclick="AppState.toggleAIRecommendation(${r.id})" title="${r.is_active ? 'סמן כהושלם' : 'החזר לפעיל'}">
                      ${r.is_active ? '✓ הושלם' : '↺ החזר'}
                    </button>
                    <button type="button" class="ai-rec-del-btn" onclick="AppState.deleteAIRecommendation(${r.id})" title="מחק המלצה זו">✕</button>
                  </div>
                </div>
                <div class="ai-rec-body">${this.escapeHtml(r.content)}</div>
              </div>
            `;
          }).join('')}
        </div>
      `;
    };

    if (profileCont) {
      profileCont.innerHTML = `
        <div class="ai-recs-panel-box">
          <div class="ai-recs-panel-header">
            <div class="ai-recs-header-left">
              <span class="ai-recs-glow-dot">●</span>
              <span class="ai-recs-section-title">המלצות והנחיות AI פעילות (${recs.filter(r => r.is_active).length})</span>
            </div>
            <button type="button" class="ai-recs-consult-btn" onclick="AppState.openAIConsultationModal()">
              💬 התייעץ עם ה-AI
            </button>
          </div>
          ${buildHtml()}
        </div>
      `;
    }

    if (nutCont) {
      nutCont.innerHTML = `
        <div class="ai-recs-panel-box">
          <div class="ai-recs-panel-header">
            <div class="ai-recs-header-left">
              <span class="ai-recs-glow-dot">●</span>
              <span class="ai-recs-section-title">המלצות תזונה והידרציה מיועץ ה-AI</span>
            </div>
            <button type="button" class="ai-recs-consult-btn" onclick="AppState.openAIConsultationModal()">
              💬 שאל שאלה
            </button>
          </div>
          ${buildHtml(4)}
        </div>
      `;
    }
  },

  async toggleAIRecommendation(id) {
    sfx.playClick();
    try {
      const res = await fetch('/api/ai/recommendations/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
      });
      if (res.ok) {
        await this.fetchAIRecommendations();
      }
    } catch (err) {
      console.warn('Toggle rec error:', err);
    }
  },

  async deleteAIRecommendation(id) {
    sfx.playClick();
    try {
      const res = await fetch(`/api/ai/recommendations?id=${id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        await this.fetchAIRecommendations();
        this.showToast('🗑️ ההמלצה נמחקה.');
      }
    } catch (err) {
      console.warn('Delete rec error:', err);
    }
  },

  // Modal helpers
  openModal(id) {
    if (id === 'awakening-modal') {
      this.openFirstTimeAwakening(true);
      return;
    }
    sfx.playClick();
    const m = document.getElementById(id);
    if (m) {
      m.classList.add('active');
      m.style.display = 'flex';
      m.style.pointerEvents = 'auto';
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
        // Protect existing local snapshot if incoming data is empty
        const existingRaw = localStorage.getItem('SOLO_HUNTER_SYSTEM_SNAPSHOT');
        if (existingRaw) {
          try {
            const existing = JSON.parse(existingRaw);
            const exCount = (existing.daily_logs || []).length + (existing.workout_logs || []).length + (existing.supplements_log || []).length;
            const newCount = (optionalData.daily_logs || []).length + (optionalData.workout_logs || []).length + (optionalData.supplements_log || []).length;
            if (exCount > 0 && newCount === 0) {
              console.warn('Prevented overwriting rich local snapshot with empty optionalData.');
              return;
            }
          } catch(e) {}
        }
        localStorage.setItem('SOLO_HUNTER_SYSTEM_SNAPSHOT', JSON.stringify(optionalData));
        localStorage.setItem('SOLO_HUNTER_SNAPSHOT_TIMESTAMP', new Date().toISOString());
        this.updateBackupUI();
        return;
      }
      const res = await fetch('/api/backup');
      if (res.ok) {
        const data = await res.json();
        // SAFEGUARD: If we have a richer snapshot in localStorage and incoming server DB is empty,
        // do not wipe client data. Instead, automatically heal the server!
        const existingRaw = localStorage.getItem('SOLO_HUNTER_SYSTEM_SNAPSHOT');
        if (existingRaw) {
          try {
            const existing = JSON.parse(existingRaw);
            const exCount = (existing.daily_logs || []).length + (existing.workout_logs || []).length + (existing.supplements_log || []).length;
            const newCount = (data.daily_logs || []).length + (data.workout_logs || []).length + (data.supplements_log || []).length;
            if (exCount > 0 && newCount === 0) {
              console.warn('Server database is empty while client has local data. Auto-healing server from local snapshot...');
              this.restoreFromLocalSnapshot(true);
              return;
            }
          } catch(e) {}
        }
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

  async checkDisasterRecovery() {
    try {
      const banner = document.getElementById('disaster-recovery-banner');
      const rawSnapshot = localStorage.getItem('SOLO_HUNTER_SYSTEM_SNAPSHOT');
      if (!rawSnapshot) {
        if (banner) banner.style.display = 'none';
        return;
      }
      const snapshot = JSON.parse(rawSnapshot);
      const snapProfile = snapshot.hunter_profile || snapshot.profile || {};
      const snapDailyLogs = snapshot.daily_logs || snapshot.logs || [];
      const snapWorkouts = snapshot.workout_logs || [];
      const snapSupps = snapshot.supplements_log || [];

      const totalSnapRecords = snapDailyLogs.length + snapWorkouts.length + snapSupps.length;
      const isServerFresh = (!this.profile || this.profile.level <= 1) && (!this.todayMeals || this.todayMeals.length === 0);

      // If server is fresh but browser snapshot has existing history or awakened profile, auto-heal!
      if (isServerFresh && (snapProfile.level > 1 || totalSnapRecords > 0 || snapProfile.is_awakened)) {
        console.log('Detected fresh server instance with existing browser snapshot. Auto-restoring...');
        const healed = await this.restoreFromLocalSnapshot(true);
        if (healed) {
          if (banner) banner.style.display = 'none';
          return;
        }
        if (banner) {
          banner.style.display = 'block';
          const subEl = document.getElementById('disaster-banner-sub');
          if (subEl) {
            subEl.innerText = `נמצא גיבוי דפדפן ברמה ${snapProfile.level || 1} עם ${totalSnapRecords} רשומות היסטוריות. שחזר עכשיו כדי לא לאבד התקדמות.`;
          }
        }
      } else {
        if (banner) banner.style.display = 'none';
      }
    } catch (e) {
      console.warn('Disaster recovery check error:', e);
    }
  },

  async restoreFromLocalSnapshot(silent = false) {
    if (!silent) sfx.playClick();
    try {
      const rawSnapshot = localStorage.getItem('SOLO_HUNTER_SYSTEM_SNAPSHOT');
      if (!rawSnapshot) {
        if (!silent) alert('לא נמצא גיבוי מקומי שמור בדפדפן.');
        return false;
      }
      const snapshot = JSON.parse(rawSnapshot);
      const res = await fetch('/api/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(snapshot)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Restore failed');
      const banner = document.getElementById('disaster-recovery-banner');
      if (banner) banner.style.display = 'none';
      if (!silent) {
        sfx.playLevelUp();
        this.showToast('✨ כל הנתונים שוחזרו בהצלחה מהגיבוי המקומי!');
        setTimeout(() => window.location.reload(), 600);
      } else {
        console.log('Auto-healed server database from local snapshot successfully.');
        this.showToast('🛡️ הנתונים סונכרנו ושוחזרו אוטומטית מהגיבוי השמור במכשיר!');
      }
      return true;
    } catch (err) {
      if (!silent) alert('שגיאה בשחזור מגיבוי מקומי: ' + err.message);
      console.warn('Restore error:', err);
      return false;
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

  // Hard cache bust & refresh for mobile browsers & PWAs
  async forceClearCacheAndReload() {
    sfx.playClick();
    try {
      if ('caches' in window) {
        const keys = await caches.keys();
        await Promise.all(keys.map(k => caches.delete(k)));
      }
      if ('serviceWorker' in navigator) {
        const regs = await navigator.serviceWorker.getRegistrations();
        for (const r of regs) {
          await r.unregister();
        }
      }
      localStorage.removeItem('SOLO_HUNTER_SYSTEM_SNAPSHOT');
    } catch (e) {
      console.warn('Cache clearance error:', e);
    }
    window.location.href = window.location.origin + window.location.pathname + '?t=' + Date.now();
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

    // Call /api/reset/full FIRST so the reset is guaranteed to execute without browser interference
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
      localStorage.removeItem('hunter_awakened');

      sfx.playLevelUp();
      alert('[SYSTEM: לידה מחדש הושלמה!]\nהצייד חזר לרמה 1 (E-Rank) וכל הסקילים אופסו לרמה 1.\nהינך מועבר למסך ההתעוררות מחדש.');
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

    if (attent && (attent.is_active || (attent.doses && attent.doses.length > 0))) {
      const isAct = attent.is_active;
      const totalDose = attent.total_dose_mg || attent.dose_mg || 20;
      const count = attent.dose_count || 1;
      const rem = attent.remaining_hours || 0;
      const pConsumed = Math.round(this.consumed?.protein || 0);
      const pTarget = this.profile?.target_protein || 160;

      let titleText = '';
      let subText = '';
      if (isAct) {
        if (count > 1) {
          titleText = `BUFF פוקוס פעיל: אטנט (${totalDose}mg סה״כ • ${count} מנות)`;
          const doseSummary = (attent.doses || []).map(d => `${d.dose_mg}mg ב-${d.timestamp}`).join(' + ');
          subText = `מנות: ${doseSummary} • נותרו כ-${rem.toFixed(1)} שעות השפעה שיא`;
        } else {
          titleText = `BUFF פוקוס פעיל: אטנט (${totalDose}mg)`;
          subText = `נלקח ב-${attent.timestamp || '09:00'} • נותרו כ-${rem.toFixed(1)} שעות שיא`;
        }
      } else {
        titleText = `מעקב אטנט (${totalDose}mg סה״כ - השפעה הסתיימה)`;
        subText = `נלקחו ${count} מנות היום. הטווח הפרמקולוגי הסתיים • לחץ להוספת מנת בוסטר חדשה`;
      }

      container.innerHTML = `
        <div class="attent-buff-card" style="${!isAct ? 'border-color:rgba(168,85,247,0.4); background:rgba(9,19,38,0.7);' : ''}">
          <div class="attent-header-row">
            <div class="attent-title-wrap">
              <span class="attent-pill-badge" style="${!isAct ? 'opacity:0.7;' : ''}">💊</span>
              <div>
                <div class="attent-buff-title" style="${!isAct ? 'color:#c084fc;' : ''}">${titleText}</div>
                <div class="attent-buff-sub">${subText}</div>
              </div>
            </div>
            <div style="display:flex; gap:6px; align-items:center;">
              <button type="button" class="attent-cancel-btn" onclick="AppState.openAttentModal()" style="border-color:#a855f7; color:#f3e8ff; background:rgba(168,85,247,0.35); font-weight:800;" title="הוסף מנת בוסטר נוספת">➕ מנה נוספת</button>
              <button type="button" class="attent-cancel-btn" onclick="AppState.openAttentModal()" style="border-color:#c084fc; color:#f3e8ff; background:rgba(168,85,247,0.18);" title="נהל או מחק מנות">📋 ניהול</button>
              <button type="button" class="attent-cancel-btn" onclick="AppState.cancelAttent()" title="נקה את כל מנות היום">✕</button>
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
              ${isAct ? '⚡ סטרס Garmin מנוטרל' : '💤 התאוששות טבעית'}
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
              <span style="font-size:12px; font-weight:700; color:#e9d5ff;">מעקב אטנט ופוקוס (Attent)</span>
              <span style="font-size:10px; color:var(--text-secondary); display:block;">נטלת אטנט היום? לחץ כאן לבחירת מינון (10, 15, 20, 30mg), שעה ורישום בוסטרים</span>
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
    const dosesListWrap = document.getElementById('attent-doses-list-wrap');
    const dosesItemsList = document.getElementById('attent-doses-items-list');
    const summaryBadge = document.getElementById('attent-total-summary-badge');
    const formHeading = document.getElementById('attent-form-heading');

    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const todayStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;

    if (dateInput) {
      dateInput.value = targetDate || todayStr;
    }

    if (timeInput) {
      timeInput.value = `${hh}:${mm}`;
    }

    // Default to 15mg or 20mg for quick next dose
    this.selectAttentDose(this.selectedAttentDose || 20);

    // Populate today's doses list if any exist
    const doses = (activeAttent && activeAttent.doses) ? activeAttent.doses : [];
    if (doses.length > 0) {
      if (dosesListWrap) dosesListWrap.style.display = 'block';
      if (summaryBadge) {
        summaryBadge.innerText = `סה״כ: ${activeAttent.total_dose_mg || activeAttent.dose_mg || 0}mg (${doses.length} מנות)`;
      }
      if (formHeading) {
        formHeading.innerText = '➕ הוסף מנת בוסטר נוספת';
      }
      if (submitBtn) {
        submitBtn.innerText = '✨ רשום מנה נוספת (+35 EXP)';
      }
      if (dosesItemsList) {
        dosesItemsList.innerHTML = doses.map((d, idx) => {
          const isAct = d.is_active;
          const statusText = isAct ? `⚡ פעיל (נותרו ${d.remaining_hours.toFixed(1)} שעות)` : `⏱️ הסתיים`;
          const contextText = d.notes ? `• ${d.notes}` : (idx === 0 ? '• מנה 1' : `• בוסטר #${idx+1}`);
          return `
            <div style="display:flex; justify-content:space-between; align-items:center; background:rgba(255,255,255,0.04); border:1px solid rgba(192,132,252,0.25); border-radius:8px; padding:7px 10px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:#7c3aed; color:#ffffff; font-size:11px; font-weight:800; padding:2px 7px; border-radius:5px;">${d.dose_mg}mg</span>
                <div style="display:flex; flex-direction:column;">
                  <span style="font-size:12px; font-weight:700; color:#ffffff;">שעה: ${d.timestamp} <span style="font-size:10px; color:#c084fc;">${contextText}</span></span>
                  <span style="font-size:10px; color:${isAct ? 'var(--hud-cyan)' : 'var(--text-dim)'};">${statusText}</span>
                </div>
              </div>
              <button type="button" onclick="AppState.deleteAttentDose(${d.id})" style="background:rgba(239,68,68,0.15); border:1px solid rgba(239,68,68,0.4); color:#fca5a5; font-size:12px; border-radius:5px; padding:3px 8px; cursor:pointer;" title="מחק מנה זו">
                🗑️
              </button>
            </div>
          `;
        }).join('');
      }
    } else {
      if (dosesListWrap) dosesListWrap.style.display = 'none';
      if (formHeading) formHeading.innerText = '➕ רשום מנת אטנט ראשונה';
      if (submitBtn) submitBtn.innerText = '⚡ שמור נטילת אטנט (הפעל BUFF)';
    }

    const cancelWrap = document.getElementById('attent-active-cancel-wrap');
    if (cancelWrap) {
      cancelWrap.style.display = (doses.length > 0) ? 'block' : 'none';
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
    const notes = document.getElementById('attent-input-notes')?.value || 'מנת אטנט';
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
        this.showToast(`[SYSTEM: מנת אטנט (${dose}mg) נרשמה בהצלחה ב-${timeVal}!]`);
        await this.fetchDailyDebrief();
        await this.fetchLongTermInsights(this.longTermWindow || 14);
        if (this.calendarDaysData) {
          await this.fetchCalendarData(this.calendarCurrentMonth);
        }
      }
    } catch (e) {
      console.warn('Network issue while logging attent, queuing offline:', e);
      this.queueOfflineAction('/api/medication/attent', 'POST', {
        dose_mg: dose,
        timestamp: timeVal,
        duration_hours: duration,
        notes: notes,
        date: dateVal
      }, `אטנט ${dose}mg`);
      sfx.playPotion();
      this.closeModal('attent-modal');
      this.showToast(`[SYSTEM: מנת אטנט (${dose}mg) נשמרה מקומית (אופליין)!]`);
    }
  },

  async deleteAttentDose(id) {
    sfx.playClick();
    if (!confirm('האם למחוק מנת אטנט זו?')) return;
    try {
      const res = await fetch(`/api/medication/attent?id=${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'שגיאת שרת במחיקת מנה');
      }
      if (data.data) {
        this.healthAdvisor = data.data;
        this.renderAll();
        sfx.playSystemNotification();
        this.showToast('✕ מנת אטנט נמחקה');
        this.openAttentModal();
        await this.fetchDailyDebrief();
        await this.fetchLongTermInsights(this.longTermWindow || 14);
        if (this.calendarDaysData) {
          await this.fetchCalendarData(this.calendarCurrentMonth);
        }
      }
    } catch (e) {
      console.error('Error in deleteAttentDose:', e);
      alert('שגיאה במחיקת מנת אטנט: ' + (e.message || e));
    }
  },

  // ============================================================
  // 📷 FOOD VISION AI — recognize food from photo
  // ============================================================
  openFoodCamera() {
    // Trigger the hidden file/camera input
    const inp = document.getElementById('food-camera-input');
    if (inp) inp.click();
  },

  async sendFoodChat() {
    const inp = document.getElementById('food-chat-input');
    const text = (inp && inp.value || '').trim();
    if (!text) return;

    // Show vision modal in loading state (reuse same modal)
    const modal = document.getElementById('vision-modal');
    const loading = document.getElementById('vision-loading');
    const resultsBody = document.getElementById('vision-results-body');
    const errorDiv = document.getElementById('vision-error');
    if (modal) {
      modal.classList.add('active');
      modal.style.display = 'flex';
      modal.style.pointerEvents = 'auto';
    }
    if (loading) loading.style.display = 'block';
    if (resultsBody) resultsBody.style.display = 'none';
    if (errorDiv) errorDiv.style.display = 'none';
    // Update modal title and loading text to indicate chat mode
    const titleEl = modal ? modal.querySelector('.modal-title') : null;
    if (titleEl) titleEl.textContent = '🤖 AI ניתח את הארוחה';
    const loadTextEl = document.getElementById('vision-loading-text');
    if (loadTextEl) loadTextEl.textContent = 'AI מנתח את הארוחה...';

    // Clear input immediately for good UX
    if (inp) inp.value = '';

    try {
      const res = await fetch('/api/food/chat-parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      const data = await res.json();
      if (loading) loading.style.display = 'none';
      if (!res.ok) throw new Error(data.error || 'שגיאת שרת');
      this.showVisionResults(data);
    } catch (e) {
      if (loading) loading.style.display = 'none';
      if (errorDiv) errorDiv.style.display = 'block';
      const msgEl = document.getElementById('vision-error-msg');
      if (msgEl) msgEl.textContent = 'שגיאה: ' + (e.message || String(e));
    }
  },

  handleCameraFile(input) {
    const file = input.files && input.files[0];
    if (!file) return;
    // Reset input so same file can be picked again
    input.value = '';
    this.recognizeFoodImage(file);
  },

  async recognizeFoodImage(file) {
    // Show modal in loading state
    const modal = document.getElementById('vision-modal');
    const loading = document.getElementById('vision-loading');
    const resultsBody = document.getElementById('vision-results-body');
    const errorDiv = document.getElementById('vision-error');
    if (modal) {
      modal.classList.add('active');
      modal.style.display = 'flex';
      modal.style.pointerEvents = 'auto';
    }
    if (loading) loading.style.display = 'block';
    if (resultsBody) resultsBody.style.display = 'none';
    if (errorDiv) errorDiv.style.display = 'none';
    const titleEl = modal ? modal.querySelector('.modal-title') : null;
    if (titleEl) titleEl.textContent = '🔍 AI זיהוי מזון מתמונה';
    const loadTextEl = document.getElementById('vision-loading-text');
    if (loadTextEl) loadTextEl.textContent = 'AI מנתח את התמונה...';

    try {
      // Convert file to base64
      const b64 = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = e => {
          // e.target.result is data:mime;base64,xxxx
          const parts = e.target.result.split(',');
          resolve(parts[1]);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });

      const res = await fetch('/api/food/recognize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_b64: b64, mime_type: file.type || 'image/jpeg' })
      });
      const data = await res.json();
      if (loading) loading.style.display = 'none';
      if (!res.ok) {
        throw new Error(data.error || 'שגיאת שרת בזיהוי תמונה');
      }
      this.showVisionResults(data);
    } catch (e) {
      if (loading) loading.style.display = 'none';
      if (errorDiv) errorDiv.style.display = 'block';
      const msgEl = document.getElementById('vision-error-msg');
      if (msgEl) msgEl.textContent = 'שגיאה: ' + (e.message || String(e));
    }
  },

  showVisionResults(data) {
    const resultsBody = document.getElementById('vision-results-body');
    const descEl = document.getElementById('vision-meal-desc');
    const listEl = document.getElementById('vision-items-list');
    const totalsEl = document.getElementById('vision-totals');

    // Store recognized items for later use
    this._visionItems = data.items || [];

    descEl.textContent = data.meal_description || 'ארוחה מזוהה על ידי AI';

    // Render each item card
    listEl.innerHTML = '';
    (data.items || []).forEach((item, idx) => {
      const conf = item.confidence === 'high' ? '🟢' : item.confidence === 'medium' ? '🟡' : '🔴';
      const card = document.createElement('div');
      card.style.cssText = 'background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:10px; padding:12px; display:flex; align-items:center; gap:12px;';
      card.innerHTML = `
        <div style="flex:1;">
          <div style="font-weight:600; font-size:14px;">${conf} ${item.name_he || item.name_en}</div>
          <div style="font-size:11px; color:var(--text-dim); margin-top:3px;">
            ~${item.estimated_grams}g · ${item.calories} קל' · P:${item.protein}g · C:${item.carbs}g · F:${item.fats}g
          </div>
        </div>
        <div style="display:flex; align-items:center; gap:6px;">
          <input type="number" value="${item.estimated_grams}" min="1" step="5"
            style="width:62px; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.15); border-radius:6px; color:#fff; padding:4px 6px; font-size:12px; text-align:center;"
            onchange="AppState.updateVisionItemGrams(${idx}, this.value)"
            title="שנה כמות בגרמים">
          <span style="font-size:10px; color:var(--text-dim);">g</span>
        </div>
      `;
      listEl.appendChild(card);
    });

    // Totals summary
    const tc = data.total_calories || 0;
    const tp = data.total_protein || 0;
    const tca = data.total_carbs || 0;
    const tf = data.total_fats || 0;
    totalsEl.innerHTML = `
      <div style="font-size:13px; font-weight:700; color:#10b981; margin-bottom:6px;">סה"כ ארוחה:</div>
      <div style="display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:8px; text-align:center;">
        <div><div style="font-size:18px; font-weight:700; color:#f59e0b;">${Math.round(tc)}</div><div style="font-size:10px; color:var(--text-dim);">קלוריות</div></div>
        <div><div style="font-size:18px; font-weight:700; color:#60a5fa;">${tp.toFixed(1)}</div><div style="font-size:10px; color:var(--text-dim);">חלבון</div></div>
        <div><div style="font-size:18px; font-weight:700; color:#a78bfa;">${tca.toFixed(1)}</div><div style="font-size:10px; color:var(--text-dim);">פחמימות</div></div>
        <div><div style="font-size:18px; font-weight:700; color:#f472b6;">${tf.toFixed(1)}</div><div style="font-size:10px; color:var(--text-dim);">שומן</div></div>
      </div>
    `;

    resultsBody.style.display = 'block';
  },

  updateVisionItemGrams(idx, newGrams) {
    if (!this._visionItems || !this._visionItems[idx]) return;
    const item = this._visionItems[idx];
    const ratio = parseFloat(newGrams) / (item.estimated_grams || 100);
    item.estimated_grams = parseFloat(newGrams);
    item.calories = Math.round(item.calories * ratio);
    item.protein = parseFloat((item.protein * ratio).toFixed(1));
    item.carbs = parseFloat((item.carbs * ratio).toFixed(1));
    item.fats = parseFloat((item.fats * ratio).toFixed(1));
    // Recalculate totals
    const tc = this._visionItems.reduce((s, i) => s + i.calories, 0);
    const tp = this._visionItems.reduce((s, i) => s + i.protein, 0);
    const tca = this._visionItems.reduce((s, i) => s + i.carbs, 0);
    const tf = this._visionItems.reduce((s, i) => s + i.fats, 0);
    this.showVisionResults({
      items: this._visionItems,
      meal_description: document.getElementById('vision-meal-desc').textContent,
      total_calories: tc, total_protein: tp, total_carbs: tca, total_fats: tf
    });
  },

  closeVisionModal() {
    sfx.playClick();
    const modal = document.getElementById('vision-modal');
    if (modal) {
      modal.classList.remove('active');
      modal.style.display = 'none';
      modal.style.pointerEvents = 'none';
    }
    this._visionItems = null;
  },

  async addAllVisionItems() {
    sfx.playClick();
    if (!this._visionItems || this._visionItems.length === 0) {
      this.closeVisionModal();
      return;
    }
    let addedCount = 0;
    for (const item of this._visionItems) {
      try {
        const body = {
          food_name: item.name_he || item.name_en || 'ארוחת AI',
          calories: item.calories || 0,
          protein: item.protein || 0,
          carbs: item.carbs || 0,
          fats: item.fats || 0,
          serving_count: 1.0,
          serving_size_g: item.estimated_grams || 100,
          meal_type: 'snack',
          notes: 'זוהה על ידי AI'
        };
        const res = await fetch('/api/nutrition/log', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        if (res.ok) addedCount++;
      } catch (e) {
        console.error('Error adding vision item:', e);
      }
    }
    this.closeVisionModal();
    sfx.playSystemNotification();
    this.showToast('✅ נוספו ' + addedCount + ' פריטי מזון לביומן!', 'success');
    
    // Refresh all dashboards and calendar
    try {
      await this.fetchTodayData();
      await this.fetchSkills();
      await this.fetchDailyDebrief();
      if (this.calendarDaysData) await this.fetchCalendarData(this.calendarCurrentMonth);
    } catch (err) {
      console.warn('Error refreshing data after adding AI food items:', err);
    }
  },

  async cancelAttent() {
    sfx.playClick();
    if (!confirm('האם לנקות ולבטל את כל מנות האטנט שנרשמו להיום?')) return;
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
        this.showToast('✕ כל מנות האטנט להיום נוקו');
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

    if (scoreVal) scoreVal.innerText = data.composite_score || '--';
    if (headlineEl) headlineEl.innerText = data.headline || '';
    if (summaryEl) summaryEl.innerText = data.summary || '';

    if (!gridEl) return;

    // Check if user is a beginner with insufficient logged days (< 3 days)
    if (data.has_sufficient_data === false || !data.pillars) {
      const b = data.beginner_onboarding || {
        title: 'מנוע ה-AI צובר נתונים ביולוגיים',
        subtitle: `תיעדת ${data.logged_days_count || 0} מתוך 3 ימי מעקב נדרשים`,
        description: 'התחלת את המסע שלך לאחרונה! כדי לספק תובנות ארוכות טווח מדויקות ואמינות (עומס אימונים, מגמת גירעון/עודף קלורי, דינמיקת דופמין והתאוששות), המערכת דורשת לפחות 3 ימי תיעוד מלאים.',
        unlock_list: [
          'עקומות מגמה של קלוריות, חלבון והוצאה אנרגטית יומית (MPS & TDEE)',
          'מדד מאזן נוזלים ואינדקס הידרציה כרוני (Hydration Baseline)',
          'התאוששות ודינמיקת רגישות קולטנים (Attent / Drug Holidays & HRV)',
          'מדד עומס שבועי והתקדמות כוח ענקים (Weekly Volume Load)'
        ],
        action_call: 'המשך לתעד את הארוחות, השתייה והאימונים בימים הקרובים. ברגע שתגיע ל-3 ימים, כל התובנות ייפתחו אוטומטית!'
      };

      const days = data.logged_days_count || 0;
      const pct = Math.min(100, Math.round((days / 3) * 100));

      gridEl.innerHTML = `
        <div class="lt-beginner-onboarding-card">
          <div class="lt-beg-header">
            <div class="lt-beg-badge">🌱 שלב צבירת נתונים ביולוגיים (${days}/3 ימים)</div>
            <h3 class="lt-beg-title">${this.escapeHtml(b.title)}</h3>
            <p class="lt-beg-sub">${this.escapeHtml(b.subtitle)}</p>
          </div>

          <div class="lt-beg-progress-section">
            <div class="lt-beg-progress-labels">
              <span>ימי פעילות מתועדים: <strong>${days} מתוך 3 ימים</strong></span>
              <span><strong>${pct}% הושלם</strong></span>
            </div>
            <div class="lt-beg-track">
              <div class="lt-beg-fill" style="width: ${pct}%"></div>
            </div>
          </div>

          <p class="lt-beg-desc">${this.escapeHtml(b.description)}</p>

          <div class="lt-beg-unlock-box">
            <div class="lt-beg-unlock-title">✨ תובנות מדעיות שייפתחו בהגעה ל-3 ימים:</div>
            <ul class="lt-beg-unlock-items">
              ${(b.unlock_list || []).map(item => `<li><span class="lt-beg-check">⚡</span> ${this.escapeHtml(item)}</li>`).join('')}
            </ul>
          </div>

          <div class="lt-beg-action-box">
            🎯 <strong>הנחיית המערכת:</strong> ${this.escapeHtml(b.action_call)}
          </div>
        </div>
      `;
      return;
    }

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

      ${p.supplements ? `
      <!-- Pillar 6: Micronutrient Shield & Supplements Consistency -->
      <div class="lt-pillar-card">
        <div class="lt-pillar-top">
          <div class="lt-pillar-title-wrap">
            <span class="lt-pillar-icon">🧪</span>
            <span class="lt-pillar-title">${p.supplements.title}</span>
          </div>
          <span class="lt-pillar-badge ${p.supplements.badge_type}">${p.supplements.badge}</span>
        </div>
        <div class="lt-pillar-stats-row">
          <span class="lt-stat-chip">ימי נטילה: <strong>${p.supplements.days_taken} ימים (${p.supplements.adherence_pct}%)</strong></span>
          <span class="lt-stat-chip">ממוצע יומי: <strong>${p.supplements.avg_supps_per_day} תוספים</strong></span>
          <span class="lt-stat-chip">מגנזיום באטנט: <strong>${p.supplements.mag_attent_pct}%</strong></span>
        </div>
        <div class="lt-pillar-insight">${p.supplements.insight}</div>
        <div class="lt-pillar-evidence-box">🔬 מחקר: ${p.supplements.citation}</div>
        <div class="lt-pillar-action-box">👉 ${p.supplements.action}</div>
      </div>
      ` : ''}
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
    } catch (e) {
      console.warn('Network issue while logging workout, queuing offline:', e);
      this.queueOfflineAction('/api/workouts/log', 'POST', {
        workout_type: wType,
        title: title,
        duration_min: duration,
        calories_burned: calories,
        notes: notes
      }, title);
      this.closeModal('workout-modal');
      sfx.playSystemNotification();
      this.showToast(`[SYSTEM: אימון (${title}) נשמר מקומית (אופליין)!]`);
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
      console.warn('Network issue while logging supplement, queuing offline:', e);
      this.queueOfflineAction('/api/supplements/log', 'POST', {
        name: name,
        dosage: dose,
        unit: 'dose',
        category: category
      }, name);
      sfx.playPotion();
      this.showToast(`[SYSTEM: ${name} נשמר מקומית (אופליין)!]`);
      if (!this.supplements) this.supplements = [];
      this.supplements.unshift({
        id: 'off_' + Date.now(),
        name: name,
        dosage: dose,
        unit: 'dose',
        category: category,
        timestamp: new Date().toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
        offline: true
      });
      this.renderSupplements();
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
    const u = (unlocked !== undefined && unlocked !== null && !isNaN(unlocked)) ? unlocked : 0;
    const t = (total !== undefined && total !== null && !isNaN(total)) ? total : 0;
    const pill = document.getElementById('badges-pill-count');
    if (pill) pill.innerText = `${u}/${t}`;
    const navPill = document.getElementById('nav-badge-pill');
    if (navPill) navPill.innerText = u;
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
  },

  // ============================================================
  // OFFLINE-FIRST QUEUE & SYNC (פיצ'ר 4)
  // ============================================================
  offlineQueue: [],
  _isFlushingQueue: false,

  initOfflineQueue() {
    try {
      this.offlineQueue = JSON.parse(localStorage.getItem('solo_offline_queue') || '[]');
    } catch (e) {
      this.offlineQueue = [];
    }
    this.updateOfflineBadge();

    window.addEventListener('online', () => {
      console.log('Network restored. Flushing offline queue...');
      this.flushOfflineQueue();
    });

    window.addEventListener('offline', () => {
      this.updateOfflineBadge();
    });

    // Auto-flush on startup if online
    if (navigator.onLine && this.offlineQueue.length > 0) {
      setTimeout(() => this.flushOfflineQueue(), 1500);
    }
  },

  updateOfflineBadge() {
    const badge = document.getElementById('offline-status-badge');
    const countEl = document.getElementById('offline-queue-count');
    const textEl = document.getElementById('offline-badge-text');
    if (!badge) return;
    const count = (this.offlineQueue || []).length;
    if (!navigator.onLine || count > 0) {
      badge.style.display = 'inline-flex';
      if (countEl) countEl.innerText = count;
      if (!navigator.onLine) {
        badge.className = 'offline-status-badge is-offline';
        if (textEl) textEl.innerHTML = `אופליין (${count})`;
        badge.title = 'אין חיבור לרשת. נתונים נשמרים מקומית ויסונכרנו אוטומטית כשהקליטה תחזור.';
      } else {
        badge.className = 'offline-status-badge is-syncing';
        if (textEl) textEl.innerHTML = `ממתין לסנכרון (${count})`;
        badge.title = `${count} פעולות ממתינות לסנכרון. לחץ כאן לסנכרון מיידי.`;
      }
    } else {
      badge.style.display = 'none';
    }
  },

  queueOfflineAction(endpoint, method, body, desc = '') {
    const action = {
      id: 'act_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5),
      endpoint,
      method: method || 'POST',
      body,
      timestamp: new Date().toISOString(),
      desc: desc || endpoint
    };
    if (!this.offlineQueue) this.offlineQueue = [];
    this.offlineQueue.push(action);
    try {
      localStorage.setItem('solo_offline_queue', JSON.stringify(this.offlineQueue));
    } catch (e) {
      console.error('Failed to save offline queue', e);
    }
    this.updateOfflineBadge();
  },

  async flushOfflineQueue() {
    if (!navigator.onLine || !this.offlineQueue || this.offlineQueue.length === 0) return;
    if (this._isFlushingQueue) return;
    this._isFlushingQueue = true;

    this.showToast(`[SYSTEM: מסנכרן ${this.offlineQueue.length} פעולות אופליין לענן...]`);
    const remaining = [];
    let syncedCount = 0;

    for (const item of this.offlineQueue) {
      try {
        const options = {
          method: item.method || 'POST',
          headers: { 'Content-Type': 'application/json' }
        };
        if (item.body && item.method !== 'GET' && item.method !== 'HEAD') {
          options.body = typeof item.body === 'string' ? item.body : JSON.stringify(item.body);
        }
        const res = await fetch(item.endpoint, options);
        if (res.ok) {
          syncedCount++;
        } else if (res.status >= 500) {
          remaining.push(item);
        }
      } catch (err) {
        remaining.push(item);
        break;
      }
    }

    this.offlineQueue = remaining;
    try {
      localStorage.setItem('solo_offline_queue', JSON.stringify(this.offlineQueue));
    } catch (e) {}
    this.updateOfflineBadge();
    this._isFlushingQueue = false;

    if (syncedCount > 0) {
      this.showToast(`✨ ${syncedCount} פעולות סונכרנו בהצלחה לענן!`);
      sfx.playLevelUp();
      await this.fetchTodayData();
      if (typeof this.fetchDailyDebrief === 'function') this.fetchDailyDebrief();
    }
  },

  // ============================================================
  // WEEKLY HUNTER DEBRIEF & WHATSAPP EXPORT (פיצ'ר 5)
  // ============================================================
  weeklyReportData: null,

  async openWeeklyReport() {
    sfx.playClick();
    this.openModal('weekly-report-modal');

    const aiEl = document.getElementById('weekly-ai-text');
    if (aiEl) aiEl.innerText = 'טוען ניתוח שבועי מקיף...';

    try {
      const res = await fetch('/api/reports/weekly');
      if (!res.ok) throw new Error('שגיאה בטעינת דוח שבועי');
      const data = await res.json();
      this.weeklyReportData = data;
      this.renderWeeklyReport(data);
    } catch (e) {
      console.error('Error fetching weekly report:', e);
      if (aiEl) aiEl.innerText = 'לא ניתן היה לטעון דוח שבועי מהשרת כרגע.';
    }
  },

  renderWeeklyReport(data) {
    if (!data) return;

    // Date range
    const rangeEl = document.getElementById('weekly-date-range-sub');
    if (rangeEl) rangeEl.innerText = `טווח תאריכים: ${data.start_date} עד ${data.end_date} (${data.active_days} ימים פעילים)`;

    // Shift badge
    const shiftBadge = document.getElementById('weekly-shift-badge');
    if (shiftBadge) shiftBadge.innerText = data.shift_label || 'סדר יום רגיל';

    // KPIs
    const calVal = document.getElementById('weekly-cal-val');
    const calSub = document.getElementById('weekly-cal-sub');
    if (calVal) calVal.innerText = `${data.avg_calories || 0} קק״ל`;
    if (calSub) calSub.innerText = `${data.cal_adherence || 0}% עמידה ביעד (${data.target_calories})`;

    const protVal = document.getElementById('weekly-prot-val');
    const protSub = document.getElementById('weekly-prot-sub');
    if (protVal) protVal.innerText = `${data.avg_protein || 0}g`;
    if (protSub) protSub.innerText = `${data.prot_adherence || 0}% עמידה ביעד (${data.target_protein}g)`;

    const waterVal = document.getElementById('weekly-water-val');
    const waterSub = document.getElementById('weekly-water-sub');
    if (waterVal) waterVal.innerText = `${data.total_water_liters || 0} ליטר`;
    if (waterSub) waterSub.innerText = `ממוצע ${data.avg_water_ml || 0} מ״ל ליום`;

    const workVal = document.getElementById('weekly-workouts-val');
    const workSub = document.getElementById('weekly-shifts-sub');
    if (workVal) workVal.innerText = `${data.workout_count || 0}`;
    if (workSub) workSub.innerText = data.workout_count > 0 ? 'אימונים תועדו' : 'לא תועדו אימונים';

    // AI takeaway
    const aiText = document.getElementById('weekly-ai-text');
    if (aiText) aiText.innerText = data.ai_insight || 'המערכת ממליצה להמשיך להקפיד על צריכת חלבון מספקת ומים לאורך כל המשמרת.';

    // Daily breakdown table
    const daysList = document.getElementById('weekly-days-list');
    if (daysList && data.daily_records) {
      daysList.innerHTML = data.daily_records.map(r => `
        <div class="weekly-day-row">
          <span style="font-weight:700; color:#94a3b8; font-size:11px;">${r.date.slice(5)}</span>
          <span style="color:#e2e8f0; font-size:11px;">🔥 ${Math.round(r.calories)} קק״ל</span>
          <span style="color:#38bdf8; font-weight:700; font-size:11px;">🥩 ${Math.round(r.protein)}g חלבון</span>
          <span style="color:#60a5fa; font-size:11px;">💧 ${r.water_ml}ml</span>
          <span style="color:#64748b; font-size:10px;">${r.meal_count} ארוחות</span>
        </div>
      `).join('');
    }
  },

  shareWeeklyWhatsApp() {
    sfx.playClick();
    if (!this.weeklyReportData || !this.weeklyReportData.whatsapp_text) {
      this.showToast('טוען דוח שבועי...');
      return;
    }
    const text = encodeURIComponent(this.weeklyReportData.whatsapp_text);
    const url = `https://api.whatsapp.com/send?text=${text}`;
    window.open(url, '_blank');
  },

  copyWeeklyReport() {
    sfx.playClick();
    if (!this.weeklyReportData || !this.weeklyReportData.whatsapp_text) return;
    navigator.clipboard.writeText(this.weeklyReportData.whatsapp_text).then(() => {
      const icon = document.getElementById('copy-report-icon');
      const txt = document.getElementById('copy-report-text');
      if (icon) icon.innerText = '✓';
      if (txt) txt.innerText = 'הועתק!';
      this.showToast('📋 דוח שבועי הועתק ללוח בהצלחה!');
      setTimeout(() => {
        if (icon) icon.innerText = '📋';
        if (txt) txt.innerText = 'העתק';
      }, 2500);
    }).catch(err => {
      console.error('Clipboard copy failed:', err);
      alert('לא ניתן היה להעתיק ישירות. אנא העתק ידנית.');
    });
  },

  printWeeklyReport() {
    sfx.playClick();
    window.print();
  }
};

window.addEventListener('DOMContentLoaded', () => {
  AppState.init();
});
