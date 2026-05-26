// Global fetch interceptor for DPR
(function() {
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
        let [resource, config] = args;
        
        config = config || {};
        // If config.headers is not present, initialize it
        if (!config.headers) {
            config.headers = {};
        }
        
        const token = localStorage.getItem('dpr_token');
        if (token) {
            if (config.headers instanceof Headers) {
                config.headers.set('Authorization', `Bearer ${token}`);
            } else {
                config.headers['Authorization'] = `Bearer ${token}`;
            }
        }
        
        try {
            const response = await originalFetch(resource, config);
            if (response.status === 401) {
                console.warn("Session expired or unauthorized (401). Redirecting to login...");
                localStorage.removeItem('dpr_token');
                localStorage.removeItem('dpr_user');
                const isAuthPage = window.location.pathname.includes('login.html') || window.location.pathname.includes('register.html');
                if (!isAuthPage) {
                    window.location.href = '/login.html';
                }
            }
            return response;
        } catch (error) {
            throw error;
        }
    };
})();

const Auth = {
    initLogin() {
        const form = document.getElementById('login-form');
        const errorDiv = document.getElementById('auth-error');

        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                errorDiv.classList.remove('visible');
                
                const email = document.getElementById('email').value;
                const password = document.getElementById('password').value;
                const btn = form.querySelector('button[type="submit"]');
                
                if (!email || !password) {
                    this.showError(errorDiv, "Please enter both email and password.");
                    return;
                }
                
                const originalText = btn.innerHTML;
                btn.innerHTML = 'Signing in...';
                btn.disabled = true;

                try {
                    const res = await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, password })
                    });

                    const data = await res.json();

                    if (res.ok) {
                        // Store mock token and redirect
                        localStorage.setItem('dpr_token', data.token);
                        localStorage.setItem('dpr_user', JSON.stringify(data.user));
                        window.location.href = '/';
                    } else {
                        this.showError(errorDiv, data.detail || 'Authentication failed');
                    }
                } catch (err) {
                    this.showError(errorDiv, 'Network error. Please try again.');
                } finally {
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }
            });
        }
    },

    initRegister() {
        const form = document.getElementById('register-form');
        const errorDiv = document.getElementById('auth-error');
        const pwdInput = document.getElementById('password');
        
        if (pwdInput) {
            pwdInput.addEventListener('input', (e) => this.checkPasswordStrength(e.target.value));
        }

        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                errorDiv.classList.remove('visible');
                
                const fullName = document.getElementById('fullname').value;
                const email = document.getElementById('email').value;
                const company = document.getElementById('company').value;
                const role = document.getElementById('role').value;
                const password = document.getElementById('password').value;
                const confirmPassword = document.getElementById('confirm-password').value;
                const terms = document.getElementById('terms').checked;
                
                if (!terms) {
                    this.showError(errorDiv, "You must agree to the Terms of Service.");
                    return;
                }
                
                if (password !== confirmPassword) {
                    this.showError(errorDiv, "Passwords do not match.");
                    return;
                }
                
                if (password.length < 6) {
                    this.showError(errorDiv, "Password must be at least 6 characters long.");
                    return;
                }
                
                const btn = form.querySelector('button[type="submit"]');
                const originalText = btn.innerHTML;
                btn.innerHTML = 'Creating Account...';
                btn.disabled = true;

                try {
                    const res = await fetch('/api/auth/register', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ 
                            full_name: fullName, 
                            email, 
                            company, 
                            role, 
                            password 
                        })
                    });

                    const data = await res.json();

                    if (res.ok) {
                        // Redirect to login
                        window.location.href = '/login.html?registered=true';
                    } else {
                        this.showError(errorDiv, data.detail || 'Registration failed');
                    }
                } catch (err) {
                    this.showError(errorDiv, 'Network error. Please try again.');
                } finally {
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }
            });
        }
    },

    checkPasswordStrength(password) {
        const bar = document.getElementById('strength-bar');
        const text = document.getElementById('strength-text');
        
        if (!bar || !text) return;
        
        if (password.length === 0) {
            bar.className = 'strength-bar';
            bar.style.width = '0%';
            text.textContent = '';
            return;
        }
        
        let strength = 0;
        if (password.length >= 6) strength += 1;
        if (password.match(/[A-Z]/)) strength += 1;
        if (password.match(/[0-9]/)) strength += 1;
        if (password.match(/[^a-zA-Z0-9]/)) strength += 1;
        
        if (strength <= 1) {
            bar.className = 'strength-bar weak';
            text.textContent = 'Weak';
        } else if (strength === 2 || strength === 3) {
            bar.className = 'strength-bar fair';
            text.textContent = 'Fair';
        } else {
            bar.className = 'strength-bar strong';
            text.textContent = 'Strong';
        }
    },

    showError(element, message) {
        if (!element) return;
        element.textContent = message;
        element.classList.add('visible');
    },

    togglePassword(inputId) {
        const input = document.getElementById(inputId);
        if (input) {
            if (input.type === 'password') {
                input.type = 'text';
            } else {
                input.type = 'password';
            }
        }
    },
    
    checkAuth() {
        const isAuthPage = window.location.pathname.includes('login.html') || window.location.pathname.includes('register.html');
        const token = localStorage.getItem('dpr_token');
        const userStr = localStorage.getItem('dpr_user');
        
        if (!isAuthPage && !token) {
            window.location.href = '/login.html';
        } else if (isAuthPage && token) {
            window.location.href = '/';
        } else if (!isAuthPage && token && userStr) {
            try {
                const user = JSON.parse(userStr);
                const greeting = document.getElementById('user-greeting');
                if (greeting) {
                    greeting.textContent = `Welcome, ${user.full_name}`;
                }
            } catch (e) {
                console.error("Error parsing user data");
            }
        }
    },
    
    logout() {
        localStorage.removeItem('dpr_token');
        localStorage.removeItem('dpr_user');
        window.location.href = '/login.html';
    }
};

// Initialize based on current page
document.addEventListener('DOMContentLoaded', () => {
    Auth.checkAuth();
    
    // Check if there's a success message from registration
    if (window.location.pathname.includes('login.html')) {
        Auth.initLogin();
        
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('registered') === 'true') {
            const errorDiv = document.getElementById('auth-error');
            if (errorDiv) {
                errorDiv.textContent = 'Account created successfully. Please sign in.';
                errorDiv.className = 'auth-error visible';
                errorDiv.style.backgroundColor = 'rgba(45, 138, 84, 0.1)';
                errorDiv.style.color = 'var(--success)';
                errorDiv.style.borderColor = 'rgba(45, 138, 84, 0.2)';
            }
        }
    } else if (window.location.pathname.includes('register.html')) {
        Auth.initRegister();
    }
});
