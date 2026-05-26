/**
 * DPR Manager — User Management Controller (Admin Only)
 * Manages the User list, Stats counters, and account operations (Create, Role modification, Password reset, and Deletions).
 */
const UserManager = (() => {
    let usersList = []; // Local cache for client-side search filtering
    
    /**
     * Display a localized toast notification.
     * Replicates the look-and-feel of the main App.js toast system.
     */
    function showToast(message, type = 'info') {
        const c = document.getElementById('toast-container');
        if (!c) return;
        const el = document.createElement('div');
        el.className = `toast toast-${type}`;
        el.textContent = message;
        c.appendChild(el);
        setTimeout(() => {
            el.style.opacity = '0';
            setTimeout(() => el.remove(), 200);
        }, 3500);
    }
    
    /**
     * Returns the currently logged in user from localStorage.
     */
    function getLoggedInUser() {
        const userStr = localStorage.getItem('dpr_user');
        if (!userStr) return null;
        try {
            return JSON.parse(userStr);
        } catch (e) {
            return null;
        }
    }

    /**
     * Fetch users list from the backend and populate the UI stats and table.
     */
    async function load() {
        try {
            const res = await fetch('/api/users');
            if (!res.ok) {
                if (res.status === 403) {
                    showToast(I18n.t('toast.unauthorized') || 'Forbidden', 'error');
                } else {
                    const err = await res.json();
                    showToast(err.detail || 'Failed to load user records', 'error');
                }
                return;
            }
            usersList = await res.json();
            updateStats();
            renderUsersTable(usersList);
        } catch (e) {
            console.error("Error loading users:", e);
            showToast("Failed to fetch users list", 'error');
        }
    }

    /**
     * Update bento-style stats cards dynamically.
     */
    function updateStats() {
        const total = usersList.length;
        const admins = usersList.filter(u => u.role === 'admin').length;
        const regular = usersList.filter(u => u.role === 'user').length;
        
        const totalEl = document.getElementById('stats-total-users');
        const adminEl = document.getElementById('stats-admin-users');
        const regularEl = document.getElementById('stats-regular-users');
        
        if (totalEl) totalEl.textContent = total;
        if (adminEl) adminEl.textContent = admins;
        if (regularEl) regularEl.textContent = regular;
    }

    /**
     * Helper to get initials for avatar placement.
     */
    function getInitials(name) {
        if (!name) return 'U';
        const parts = name.trim().split(/\s+/);
        if (parts.length >= 2) {
            return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
        }
        return parts[0][0].toUpperCase();
    }

    /**
     * Localized date time formatter.
     */
    function formatDateTime(isoString) {
        if (!isoString) return '—';
        try {
            const d = new Date(isoString);
            const isFr = I18n.lang() === 'fr';
            return d.toLocaleDateString(isFr ? 'fr-FR' : 'en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return isoString;
        }
    }

    /**
     * Render the list of users inside the directory layout.
     */
    function renderUsersTable(list) {
        const tbody = document.getElementById('users-tbody');
        if (!tbody) return;
        
        if (list.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="empty-row" style="padding: 40px; text-align: center; color: var(--text-secondary);">${I18n.lang() === 'fr' ? 'Aucun utilisateur trouvé' : 'No users found'}</td></tr>`;
            return;
        }

        const currentUser = getLoggedInUser();

        tbody.innerHTML = list.map(u => {
            const initials = getInitials(u.full_name);
            const isSelf = currentUser && currentUser.id === u.id;
            const roleKey = u.role === 'admin' ? 'users.role.admin' : 'users.role.user';
            const roleText = I18n.t(roleKey);
            
            // Warm off-white canvas/charcoal design matching aesthetic details
            const roleBadgeStyle = u.role === 'admin' 
                ? 'background: rgba(44, 44, 44, 0.08); color: var(--text-primary); border: 1px solid rgba(44, 44, 44, 0.15);' 
                : 'background: rgba(255, 255, 255, 0.4); color: var(--text-muted); border: 1px solid rgba(0, 0, 0, 0.08);';
            
            const trStyle = isSelf ? 'background: rgba(255, 255, 255, 0.15);' : '';
            const selfBadge = isSelf ? ` <span style="font-size: 0.7rem; padding: 2px 6px; border-radius: 10px; background: rgba(0,0,0,0.05); color: var(--text-secondary); font-weight: 500; margin-left: 6px;">${I18n.lang() === 'fr' ? 'Vous' : 'You'}</span>` : '';

            // Actions - Safety checks to prevent self-deletion or last admin deletion
            const deleteBtn = isSelf 
                ? `<button class="btn btn-sm btn-ghost" disabled style="opacity: 0.4; cursor: not-allowed; filter: grayscale(1);" title="${I18n.lang() === 'fr' ? 'Impossible de supprimer votre propre compte' : 'Cannot delete your own account'}">🗑️</button>`
                : `<button class="btn btn-sm btn-outline" onclick="UserManager.deleteUser(${u.id}, '${u.full_name.replace(/'/g, "\\'")}')" title="${I18n.t('users.action.delete')}" style="padding: 4px 8px; border-radius: var(--radius-xs); border: 1px solid var(--border); font-size: 0.8rem; cursor: pointer; transition: all 0.2s; color: var(--danger); border-color: rgba(192, 57, 43, 0.2);" onmouseover="this.style.background='rgba(192,57,43,0.05)';" onmouseout="this.style.background='transparent';">🗑️</button>`;

            return `
                <tr style="${trStyle} border-bottom: 1px solid var(--border); transition: background 0.15s;" onmouseover="this.style.background='rgba(255,255,255,0.25)'" onmouseout="this.style.background='${isSelf ? 'rgba(255,255,255,0.15)' : 'transparent'}'">
                    <td style="padding: 12px 20px; display: flex; align-items: center; gap: 12px;">
                        <div style="width: 38px; height: 38px; border-radius: 50%; background: rgba(0, 0, 0, 0.05); border: 1px solid rgba(0, 0, 0, 0.08); display: flex; align-items: center; justify-content: center; font-weight: 600; color: var(--text-primary); font-size: 0.85rem; letter-spacing: 0.05em; backdrop-filter: blur(5px);">
                            ${initials}
                        </div>
                        <div>
                            <div style="font-weight: 600; color: var(--text-primary); display: flex; align-items: center;">${u.full_name}${selfBadge}</div>
                            <div style="font-size: 0.78rem; color: var(--text-muted);">${u.email}</div>
                        </div>
                    </td>
                    <td style="padding: 12px 20px; color: var(--text-primary); font-weight: 500;">
                        ${u.company || '—'}
                    </td>
                    <td style="padding: 12px 20px;">
                        <span style="display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; ${roleBadgeStyle}">
                            ${roleText}
                        </span>
                    </td>
                    <td style="padding: 12px 20px; color: var(--text-muted); font-size: 0.8rem;">
                        ${formatDateTime(u.created_at)}
                    </td>
                    <td style="padding: 12px 20px; text-align: right;">
                        <div style="display: inline-flex; gap: 6px; align-items: center;">
                            <button class="btn btn-sm btn-outline" onclick="UserManager.openEditRoleModal(${u.id}, '${u.full_name.replace(/'/g, "\\'")}', '${u.role}')" title="${I18n.t('users.action.edit_role')}" style="padding: 4px 8px; border-radius: var(--radius-xs); border: 1px solid var(--border); font-size: 0.8rem; cursor: pointer; transition: all 0.2s;">🛡️</button>
                            <button class="btn btn-sm btn-outline" onclick="UserManager.openResetPasswordModal(${u.id}, '${u.full_name.replace(/'/g, "\\'")}')" title="${I18n.t('users.action.reset_pwd')}" style="padding: 4px 8px; border-radius: var(--radius-xs); border: 1px solid var(--border); font-size: 0.8rem; cursor: pointer; transition: all 0.2s;">🔑</button>
                            ${deleteBtn}
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    /**
     * Performs a client-side search across Name, Email, and Company fields.
     */
    function filterUsers() {
        const input = document.getElementById('search-users');
        if (!input) return;
        const q = input.value.trim().toLowerCase();
        if (!q) {
            renderUsersTable(usersList);
            return;
        }
        
        const filtered = usersList.filter(u => {
            return (u.full_name || '').toLowerCase().includes(q) || 
                   (u.email || '').toLowerCase().includes(q) || 
                   (u.company || '').toLowerCase().includes(q);
        });
        renderUsersTable(filtered);
    }

    /**
     * Overlay modal managers
     */
    function openAddModal() {
        closeModals();
        
        // Reset form inputs & clear errors
        const form = document.getElementById('form-add-user');
        if (form) form.reset();
        
        const errDiv = document.getElementById('add-user-error');
        if (errDiv) {
            errDiv.style.display = 'none';
            errDiv.textContent = '';
        }
        
        const m = document.getElementById('modal-add-user');
        if (m) {
            m.style.display = 'flex';
        }
    }

    function openEditRoleModal(id, name, role) {
        closeModals();
        
        const idInput = document.getElementById('edit-role-userid');
        const nameSpan = document.getElementById('edit-role-username');
        const roleSelect = document.getElementById('edit-role-select');
        
        if (idInput) idInput.value = id;
        if (nameSpan) nameSpan.textContent = name;
        if (roleSelect) roleSelect.value = role;
        
        const errDiv = document.getElementById('edit-role-error');
        if (errDiv) {
            errDiv.style.display = 'none';
            errDiv.textContent = '';
        }
        
        const m = document.getElementById('modal-edit-role');
        if (m) {
            m.style.display = 'flex';
        }
    }

    function openResetPasswordModal(id, name) {
        closeModals();
        
        const idInput = document.getElementById('reset-pwd-userid');
        const nameSpan = document.getElementById('reset-pwd-username');
        const pwdInput = document.getElementById('reset-pwd-input');
        
        if (idInput) idInput.value = id;
        if (nameSpan) nameSpan.textContent = name;
        if (pwdInput) pwdInput.value = '';
        
        const errDiv = document.getElementById('reset-pwd-error');
        if (errDiv) {
            errDiv.style.display = 'none';
            errDiv.textContent = '';
        }
        
        const m = document.getElementById('modal-reset-password');
        if (m) {
            m.style.display = 'flex';
        }
    }

    function closeModals() {
        const modals = ['modal-add-user', 'modal-edit-role', 'modal-reset-password'];
        modals.forEach(id => {
            const m = document.getElementById(id);
            if (m) m.style.display = 'none';
        });
    }

    /**
     * Delete user action (prevents deleting active logged-in user)
     */
    async function deleteUser(id, name) {
        const confirmMsg = I18n.t('users.confirm.delete');
        if (!confirm(`${confirmMsg} (${name})`)) return;
        
        try {
            const res = await fetch(`/api/users/${id}`, {
                method: 'DELETE'
            });
            const data = await res.json();
            if (res.ok) {
                showToast(I18n.t('users.toast.deleted'), 'success');
                load();
            } else {
                showToast(data.detail || 'Delete failed', 'error');
            }
        } catch (e) {
            console.error("Delete user error:", e);
            showToast("Failed to delete user account", 'error');
        }
    }

    /**
     * Wire forms event handlers
     */
    function initListeners() {
        // Form Add User submission
        const formAdd = document.getElementById('form-add-user');
        const addError = document.getElementById('add-user-error');
        if (formAdd) {
            formAdd.addEventListener('submit', async (e) => {
                e.preventDefault();
                if (addError) addError.style.display = 'none';
                
                const fullName = document.getElementById('add-fullname').value.trim();
                const email = document.getElementById('add-email').value.trim();
                const company = document.getElementById('add-company').value.trim();
                const password = document.getElementById('add-password').value;
                const role = document.getElementById('add-role').value;
                
                try {
                    const res = await fetch('/api/users', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            full_name: fullName,
                            email: email,
                            company: company,
                            role: role,
                            password: password
                        })
                    });
                    const data = await res.json();
                    if (res.ok) {
                        showToast(I18n.t('users.toast.created'), 'success');
                        closeModals();
                        load();
                    } else {
                        if (addError) {
                            addError.textContent = data.detail || 'Failed to create user account';
                            addError.style.display = 'block';
                        }
                    }
                } catch (err) {
                    if (addError) {
                        addError.textContent = 'Network error. Please try again.';
                        addError.style.display = 'block';
                    }
                }
            });
        }

        // Form Edit Role submission
        const formEdit = document.getElementById('form-edit-role');
        const editError = document.getElementById('edit-role-error');
        if (formEdit) {
            formEdit.addEventListener('submit', async (e) => {
                e.preventDefault();
                if (editError) editError.style.display = 'none';
                
                const id = document.getElementById('edit-role-userid').value;
                const role = document.getElementById('edit-role-select').value;
                
                try {
                    const res = await fetch(`/api/users/${id}/role`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ role })
                    });
                    const data = await res.json();
                    if (res.ok) {
                        showToast(I18n.t('users.toast.role_updated'), 'success');
                        closeModals();
                        load();
                    } else {
                        if (editError) {
                            editError.textContent = data.detail || 'Failed to update user role';
                            editError.style.display = 'block';
                        }
                    }
                } catch (err) {
                    if (editError) {
                        editError.textContent = 'Network error. Please try again.';
                        editError.style.display = 'block';
                    }
                }
            });
        }

        // Form Reset Password submission
        const formReset = document.getElementById('form-reset-password');
        const resetError = document.getElementById('reset-pwd-error');
        if (formReset) {
            formReset.addEventListener('submit', async (e) => {
                e.preventDefault();
                if (resetError) resetError.style.display = 'none';
                
                const id = document.getElementById('reset-pwd-userid').value;
                const password = document.getElementById('reset-pwd-input').value;
                
                try {
                    const res = await fetch(`/api/users/${id}/reset-password`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ password })
                    });
                    const data = await res.json();
                    if (res.ok) {
                        showToast(I18n.t('users.toast.pwd_reset'), 'success');
                        closeModals();
                        load();
                    } else {
                        if (resetError) {
                            resetError.textContent = data.detail || 'Failed to reset password';
                            resetError.style.display = 'block';
                        }
                    }
                } catch (err) {
                    if (resetError) {
                        resetError.textContent = 'Network error. Please try again.';
                        resetError.style.display = 'block';
                    }
                }
            });
        }
    }

    // Set up event listeners when the script is loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initListeners);
    } else {
        initListeners();
    }

    return {
        load,
        filterUsers,
        openAddModal,
        openEditRoleModal,
        openResetPasswordModal,
        closeModals,
        deleteUser
    };
})();
