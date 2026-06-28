/**
 * 算法大陆 前后端集成桥梁
 * 连接 quest-mode.html 前端与 FastAPI 后端 API
 * 通过 ApiClient 发起所有请求，管理认证令牌与本地状态
 */
(function () {
  'use strict';

  const STORAGE_KEY = 'algoKingdomQuestV2';

  // ============================================================
  // 工具函数
  // ============================================================

  /** 页面加载后若存在 showToast 则显示提示，否则静默 */
  function toast(type, title, detail) {
    if (typeof showToast === 'function') {
      showToast(type, title, detail);
    } else {
      console.warn('[App] Toast:', type, title, detail);
    }
  }

  /** 安全 JSON 解析 */
  function safeJSON(str) {
    try {
      return JSON.parse(str);
    } catch (_) {
      return null;
    }
  }

  // ============================================================
  // App 全局对象
  // ============================================================
  window.App = {
    // ---------- Auth ----------
    token: null,
    user: null,

    isLoggedIn() {
      return !!this.token;
    },

    async login(username, password) {
      try {
        const data = await ApiClient.auth.login(username, password);
        this.token = data.access_token;
        this.user = data.user;
        ApiClient.setToken(data.access_token);
        this.saveState();
        return data;
      } catch (err) {
        toast('error', '登录失败', err.message || '请检查用户名和密码');
        throw err;
      }
    },

    async register(username, password) {
      try {
        const data = await ApiClient.auth.register(username, password);
        this.token = data.access_token;
        this.user = data.user;
        ApiClient.setToken(data.access_token);
        this.saveState();
        return data;
      } catch (err) {
        toast('error', '注册失败', err.message || '请稍后重试');
        throw err;
      }
    },

    logout() {
      this.token = null;
      this.user = null;
      ApiClient.clearToken();
      this.saveState();
    },

    // ---------- Data Loading ----------

    /**
     * 加载王国列表 — 纯后端数据，前端不再有任何硬编码
     * API 已返回完整数据：id/name/emoji/color/bg/glow/chaos/stats
     * @returns {Promise<Array>} 王国数组
     */
    async loadKingdoms() {
      try {
        const apiKingdoms = await ApiClient.problems.kingdoms();
        if (!apiKingdoms || !apiKingdoms.length) {
          console.warn('[App] 后端未返回王国数据');
          return [];
        }

        // 后端已是唯一数据源 — 直接透传，无需合并
        // 同时缓存原始数据（含 name），供 loadProblems 做 ID→name 反查
        this._kingdomCache = apiKingdoms;

        return apiKingdoms.map(function (api) {
          return {
            id: api.id || api.name,
            name: api.name,
            emoji: api.emoji || '🏰',
            color: api.color || '#94a3b8',
            bg: api.bg || '#1a1c20',
            glow: api.glow || 'rgba(148,163,184,.25)',
            chaos: api.chaos || false,
            tags: api.tags || [],
            total: api.total_problems || 0,
            easy: api.easy_count || 0,
            medium: api.medium_count || 0,
            hard: api.hard_count || 0,
          };
        });
      } catch (err) {
        toast('error', '加载王国失败', err.message || '请检查后端是否启动');
        return [];
      }
    },

    /**
     * 加载某个王国下的题目列表
     * @param {string} kingdom - 王国 ID（直接来自后端 API 的 id 字段）
     * @returns {Promise<Array>}
     */
    async loadProblems(kingdom) {
      try {
        // 后端 kingdom 筛选用 kingdom name（中文名），需从缓存恢复
        var backendName = kingdom;
        if (this._kingdomCache) {
          var k = this._kingdomCache.find(function (k) { return k.id === kingdom; });
          if (k) backendName = k.name;
        }

        var all = [];
        for (var page = 1; page <= 4; page++) {
          var data = await ApiClient.problems.list({
            kingdom: backendName,
            page: page,
            page_size: 50,
          });

          if (data.problems && data.problems.length) {
            all = all.concat(data.problems);
          }

          if (!data.problems || data.problems.length < 50) break;
        }

        return all.map(function (p) {
          return {
            id: p.id,
            number: p.number,
            title: p.title_cn || p.title,
            titleEn: p.title,
            difficulty: p.difficulty,
            tags: p.tags || [],
            kingdom: p.kingdom,
            kingdomEmoji: p.kingdom_emoji || '🏰',
            acRate: p.ac_rate || 0,
            enemy: p.difficulty === 'easy' ? '👾' : (p.difficulty === 'medium' ? '🐺' : '🐉'),
          };
        });
      } catch (err) {
        toast('error', '加载题目失败', err.message || '');
        return [];
      }
    },

    /**
     * 加载单个题目详情
     * @param {number|string} id - problem id
     * @returns {Promise<object>}
     */
    async loadProblemDetail(id) {
      try {
        var data = await ApiClient.problems.detail(id);
        return {
          id: data.id,
          number: data.number,
          title: data.title,
          title_cn: data.title_cn || data.title,
          difficulty: data.difficulty,
          tags: data.tags || [],
          description_html: data.description_html || '',
          description_cn_html: data.description_cn_html || '',
          hints: data.hints || [],
          solutions: data.solutions || {},
          kingdom: data.kingdom || '',
          ac_rate: data.ac_rate || 0,
        };
      } catch (err) {
        toast('error', '加载题目详情失败', err.message || '');
        throw err;
      }
    },

    /**
     * AI 语义搜索题目
     * @param {string} query
     * @returns {Promise<Array>}
     */
    async searchProblems(query) {
      try {
        var data = await ApiClient.problems.search(query);
        return (data.results || []).map(function (r) {
          var p = r.problem;
          return {
            id: p.id,
            number: p.number,
            title: p.title_cn || p.title,
            titleEn: p.title,
            difficulty: p.difficulty,
            tags: p.tags || [],
            kingdom: p.kingdom,
            kingdomEmoji: p.kingdom_emoji || '🏰',
            relevance: r.relevance || 0,
          };
        });
      } catch (err) {
        toast('error', '搜索失败', err.message || '');
        return [];
      }
    },

    // ---------- AI Assistant ----------

    /**
     * 向 AI 助手提问
     * @param {string} message
     * @param {number|string} [problemId]
     * @returns {Promise<{reply: string, coins: number, coinsSpent: number, coinsRemaining: number}>}
     */
    async askAssistant(message, problemId) {
      try {
        var data = await ApiClient.assistant.chat(message, { problem_id: problemId });
        return {
          reply: data.message || data.reply || '',
          coins: data.coins_remaining || 0,
          coinsSpent: data.coins_spent || 0,
          coinsRemaining: data.coins_remaining || 0,
        };
      } catch (err) {
        toast('error', 'AI 助手请求失败', err.message || '');
        throw err;
      }
    },

    /**
     * 获取 AI 提示
     * @param {number|string} problemId
     * @param {string} level - 'hint' | 'guide' | 'explain'
     * @returns {Promise<{reply: string, coins: number}>}
     */
    async getHint(problemId, level) {
      try {
        level = level || 'hint';
        var data = await ApiClient.assistant.getHint(problemId, level);
        return {
          reply: data.message || data.reply || '',
          coins: data.coins_remaining || 0,
        };
      } catch (err) {
        toast('error', '获取提示失败', err.message || '');
        throw err;
      }
    },

    // ---------- Submission ----------

    /**
     * 提交代码
     * @param {number|string} problemId
     * @param {string} title
     * @param {string} language
     * @param {string} code
     * @returns {Promise<object>}
     */
    async submitCode(problemId, title, language, code) {
      try {
        var data = await ApiClient.progress.submit(problemId, title, language, code);

        // 本地记录已解决
        var num = String(problemId);
        if (data.status === 'accepted' && this.state.solvedProblems.indexOf(num) === -1) {
          this.state.solvedProblems.push(num);
          this.saveState();
        }

        return data;
      } catch (err) {
        toast('error', '提交失败', err.message || '');
        throw err;
      }
    },

    // ---------- User Data ----------

    /**
     * 从后端获取已解决题目 ID 列表
     * @returns {Promise<Array<string>>}
     */
    async getSolvedIds() {
      try {
        var data = await ApiClient.progress.solved();
        var ids = (data.solved || []).map(function (id) { return String(id); });

        // 合并到本地状态
        ids.forEach(function (id) {
          if (this.state.solvedProblems.indexOf(id) === -1) {
            this.state.solvedProblems.push(id);
          }
        }, this);
        this.saveState();

        return this.state.solvedProblems;
      } catch (err) {
        return this.state.solvedProblems;
      }
    },

    /**
     * 刷新当前用户信息
     * @returns {Promise}
     */
    async refreshUser() {
      try {
        var data = await ApiClient.auth.me();
        this.user = data;
        return data;
      } catch (err) {
        throw err;
      }
    },

    // ---------- Local State (backward compat) ----------

    state: {
      currentMode: 'free',
      solvedProblems: [],
      adventureStage: 1,
      currentKingdom: null,
      currentLevel: null,
      currentLanguage: 'python',
      currentPlaylistId: null,
    },

    saveState() {
      try {
        var data = {
          solvedProblems: this.state.solvedProblems,
          adventureStage: this.state.adventureStage,
          currentMode: this.state.currentMode,
          // 保存认证信息以便恢复会话
          token: this.token,
          user: this.user,
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      } catch (_) { /* storage full or disabled */ }
    },

    loadState() {
      try {
        var raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return;

        var parsed = safeJSON(raw);
        if (!parsed) return;

        if (Array.isArray(parsed.solvedProblems)) {
          this.state.solvedProblems = parsed.solvedProblems;
        }
        if (typeof parsed.adventureStage === 'number') {
          this.state.adventureStage = parsed.adventureStage;
        }
        if (parsed.currentMode) {
          this.state.currentMode = parsed.currentMode;
        }
        // 恢复认证会话
        if (parsed.token) {
          this.token = parsed.token;
          this.user = parsed.user || null;
          ApiClient.setToken(parsed.token);
        }
      } catch (_) { /* corrupt data */ }
    },

    // ---------- Init ----------

    /**
     * 页面加载时调用，从 localStorage 恢复状态与认证会话
     */
    _init() {
      this.loadState();
      // 如果 ApiClient 已有 token（从 api-client.js 自身的 localStorage 读取），确保 App 同步
      var existingToken = ApiClient.getToken();
      if (existingToken && !this.token) {
        this.token = existingToken;
        // token 有了但 user 没有 → 尝试静默刷新
        this.refreshUser().then(function () {
          this.saveState();
        }.bind(this)).catch(function () {
          // 静默失败 - user 信息可能不可用
        });
      }
    },
  };

  // 页面加载完成后自动初始化（DOMContentLoaded 后执行）
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      window.App._init();
    });
  } else {
    window.App._init();
  }
})();
