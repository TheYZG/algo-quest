/**
 * 算法大陆 API 客户端
 * 所有前端页面的统一接口层
 */
const API_BASE = 'http://localhost:8000/api';

const ApiClient = {
    token: null,

    setToken(token) {
        this.token = token;
        localStorage.setItem('auth_token', token);
    },

    getToken() {
        if (!this.token) {
            this.token = localStorage.getItem('auth_token');
        }
        return this.token;
    },

    clearToken() {
        this.token = null;
        localStorage.removeItem('auth_token');
    },

    async request(method, path, body = null) {
        const headers = { 'Content-Type': 'application/json' };
        const token = this.getToken();
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const res = await fetch(`${API_BASE}${path}`, {
            method,
            headers,
            body: body ? JSON.stringify(body) : null,
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            let msg;
            if (typeof err.detail === 'string') {
                msg = err.detail;
            } else if (Array.isArray(err.detail)) {
                // FastAPI validation errors: [{loc, msg, type}, ...]
                msg = err.detail.map(d => d.msg).join('; ');
            } else if (err.detail) {
                msg = JSON.stringify(err.detail);
            } else if (err.message) {
                msg = err.message;
            } else {
                msg = `HTTP ${res.status}`;
            }
            throw new Error(msg);
        }

        return res.json();
    },

    // ========== 认证 ==========
    auth: {
        register(username, password, email) {
            return ApiClient.request('POST', '/auth/register', { username, password, email });
        },
        login(username, password) {
            return ApiClient.request('POST', '/auth/login', { username, password });
        },
        me() {
            return ApiClient.request('GET', '/auth/me');
        },
        stats() {
            return ApiClient.request('GET', '/auth/stats');
        },
    },

    // ========== 题目 ==========
    problems: {
        list({ page = 1, page_size = 20, difficulty, kingdom, tags } = {}) {
            const params = new URLSearchParams({ page, page_size });
            if (difficulty) params.set('difficulty', difficulty);
            if (kingdom) params.set('kingdom', kingdom);
            if (tags) params.set('tags', tags);
            return ApiClient.request('GET', `/problems?${params}`);
        },
        detail(id) {
            return ApiClient.request('GET', `/problems/${id}`);
        },
        kingdoms() {
            return ApiClient.request('GET', '/problems/meta/kingdoms');
        },
        tags() {
            return ApiClient.request('GET', '/problems/meta/tags');
        },

        // 🔍 AI 语义搜索
        search(query, { top_k = 10, difficulty, tags } = {}) {
            return ApiClient.request('POST', '/problems/search', {
                query,
                top_k,
                difficulty,
                tags,
            });
        },
    },

    // ========== AI助手 ==========
    assistant: {
        chat(message, { problem_id, problem_context, history } = {}) {
            return ApiClient.request('POST', '/assistant/chat', {
                message,
                problem_id,
                problem_context,
                history,
            });
        },
        getHint(problem_id, level = 'hint') {
            return ApiClient.request('POST', '/assistant/hint', { problem_id, level });
        },
        history(problem_id) {
            const params = problem_id ? `?problem_id=${problem_id}` : '';
            return ApiClient.request('GET', `/assistant/history${params}`);
        },
    },

    // ========== 进度 ==========
    progress: {
        submit(problem_id, problem_title, language, code) {
            return ApiClient.request('POST', '/progress/submit', {
                problem_id,
                problem_title,
                language,
                code,
            });
        },
        submissions(problem_id) {
            const params = problem_id ? `?problem_id=${problem_id}` : '';
            return ApiClient.request('GET', `/progress/submissions${params}`);
        },
        solved() {
            return ApiClient.request('GET', '/progress/solved');
        },
    },
};

// 导出到全局
window.ApiClient = ApiClient;
