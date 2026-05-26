/**
 * DPR Manager — Internationalization (EN / FR)
 *
 * Usage:  Add  data-i18n="key"  to any element.
 *         Call  I18n.set('fr')  or  I18n.set('en')  to switch.
 */
const I18n = (() => {
    const translations = {
        // ── Sidebar ────────────────────────────────────────────
        'sidebar.title':        { en: 'DPR Manager',           fr: 'Gestionnaire DPR' },
        'sidebar.subtitle':     { en: 'ETAP Production Data',  fr: 'Données de Production ETAP' },
        'nav.dashboard':        { en: 'Dashboard',             fr: 'Tableau de Bord' },
        'nav.extract':          { en: 'Extract & Process',     fr: 'Extraction & Traitement' },
        'nav.upload':           { en: 'Upload Files',          fr: 'Importer des Fichiers' },
        'nav.dc':               { en: 'Daily Concession',      fr: 'Concession Journalière' },
        'nav.dw':               { en: 'Daily Well',            fr: 'Puits Journalier' },
        'nav.mc':               { en: 'Monthly',               fr: 'Mensuel' },
        'nav.wt':               { en: 'Well Test',             fr: 'Test de Puits' },

        'nav.logs':             { en: 'Logs',                  fr: 'Journaux' },
        'sidebar.status.loaded':{ en: 'System Ready',         fr: 'Système prêt' },
        'sidebar.status.required':{en:'Setup required',        fr: 'Configuration requise' },
        'sidebar.status.connecting':{en:'Connecting...',       fr: 'Connexion...' },
        'sidebar.status.reconnecting':{en:'Reconnecting...',   fr: 'Reconnexion...' },
        'sidebar.status.connected':{en:'System Ready',         fr: 'Système prêt' },

        // ── Section titles ─────────────────────────────────────
        'section.overview':     { en: 'Overview',              fr: 'Vue d\'ensemble' },
        'section.workflow':     { en: 'Workflow',              fr: 'Flux de travail' },
        'section.results':      { en: 'Results',               fr: 'Résultats' },


        // ── Dashboard — Production Analytics ──────────────────
        'dash.filter_extraction':{ en: 'Extraction',           fr: 'Extraction' },
        'dash.filter_concession':{ en: 'Concession',           fr: 'Concession' },
        'dash.gas_prod':         { en: 'Gas Production',       fr: 'Production Gaz' },
        'dash.oil_prod':         { en: 'Oil Production',       fr: 'Production Huile' },
        'dash.water_prod':       { en: 'Water Production',     fr: 'Production Eau' },
        'dash.condensate':       { en: 'Condensate',           fr: 'Condensat' },
        'dash.total_records':    { en: 'Total Records',        fr: 'Total Enregistrements' },
        'dash.prod_by_conc':     { en: 'Production by Concession', fr: 'Production par Concession' },
        'dash.gas_dist':         { en: 'Gas Distribution',     fr: 'Distribution du Gaz' },
        'dash.liquid_products':  { en: 'Liquid Products',      fr: 'Produits Liquides' },
        'dash.production_mix':   { en: 'Production Mix',       fr: 'Mix de Production' },
        'dash.top_wells':        { en: 'Top Wells Production Performance', fr: 'Performance de Production des Puits' },
        'dash.well_name':        { en: 'Well Name',            fr: 'Nom du Puits' },
        'dash.concession':       { en: 'Concession',           fr: 'Concession' },
        'dash.water_cut':        { en: 'Water Cut %',          fr: '% Coupe d\'Eau' },
        'dash.no_well_data':     { en: 'No well data available', fr: 'Aucune donnée de puits' },
        'btn.refresh':          { en: '↻ Refresh',             fr: '↻ Actualiser' },


        // ── Extract page ───────────────────────────────────────
        'pipe.configure':       { en: 'Configure',             fr: 'Configurer' },
        'pipe.extract':         { en: 'Extract',               fr: 'Extraire' },
        'pipe.clean':           { en: 'Clean',                 fr: 'Nettoyer' },
        'pipe.export':          { en: 'Export',                 fr: 'Exporter' },

        'step1.title':          { en: 'Folder Paths',          fr: 'Chemins des Dossiers' },
        'step1.dpr':            { en: 'DPR Files Folder',      fr: 'Dossier Fichiers DPR' },
        'step1.mapping':        { en: 'Mapping Files Folder',  fr: 'Dossier Fichiers Mapping' },
        'step1.output':         { en: 'Output CSV Folder',     fr: 'Dossier de Sortie CSV' },
        'btn.save':             { en: '💾 Save',               fr: '💾 Sauvegarder' },

        'step2.title':          { en: 'Extraction Settings',   fr: 'Paramètres d\'Extraction' },
        'panel.report':         { en: 'Report',                fr: 'Rapport' },
        'panel.date':           { en: 'Date',                  fr: 'Date' },
        'panel.dpr_files':      { en: 'DPR Files',             fr: 'Fichiers DPR' },

        'type.daily_short':     { en: 'Daily',                 fr: 'Journalier' },
        'type.monthly_short':   { en: 'Monthly',               fr: 'Mensuel' },
        'type.well_test_short': { en: 'Well Test',             fr: 'Test de Puits' },
        'type.daily':           { en: 'Daily (DC + DW)',       fr: 'Journalier (DC + DW)' },
        'type.monthly':         { en: 'Monthly (MC)',          fr: 'Mensuel (MC)' },
        'type.well_test':       { en: 'Well Test (WT)',        fr: 'Test de Puits (WT)' },

        'date.dpr':             { en: 'Date DPR',              fr: 'Date DPR' },
        'date.selection':       { en: 'Selection Date',        fr: 'Date de Sélection' },

        'name.standard':        { en: 'Standard Name',         fr: 'Nom Standard' },
        'name.auto':            { en: 'Auto detect name',      fr: 'Détection auto du nom' },
        'name.multiple':        { en: 'Multiple DPR files',    fr: 'Fichiers DPR multiples' },

        'field.report_type':    { en: 'Report Type',           fr: 'Type de Rapport' },
        'field.date':           { en: 'DPR Date',              fr: 'Date DPR' },
        'field.num_days':       { en: 'Number of Days',        fr: 'Nombre de Jours' },
        'opt.autoname':         { en: 'Auto filenames',        fr: 'Noms auto' },
        'opt.concatenate':      { en: 'Concatenate',           fr: 'Concaténer' },

        'btn.extract':          { en: '⚙️ Extract',            fr: '⚙️ Extraire' },
        'btn.clean':            { en: '✓ Auto Correct',        fr: '✓ Correction Auto' },
        'btn.convert':          { en: '🔄 SM3 ↔ NM3',         fr: '🔄 SM3 ↔ NM3' },
        'btn.export':           { en: '📤 Export CSV',          fr: '📤 Exporter CSV' },
        'btn.prepare':          { en: '📂 Prepare Files',       fr: '📂 Préparer Fichiers' },
        'btn.clear_data':       { en: '✗ Clear',               fr: '✗ Effacer' },

        'extract.logs':         { en: 'Live Logs',             fr: 'Journaux en Direct' },
        'extract.preview':      { en: 'Preview',               fr: 'Aperçu' },
        'extract.no_data':      { en: 'Run an extraction to preview data', fr: 'Lancez une extraction pour prévisualiser' },

        // ── Upload page ────────────────────────────────────────
        'upload.drop':          { en: 'Drag & drop files here, or', fr: 'Glissez-déposez vos fichiers ici, ou' },
        'upload.browse':        { en: 'click to browse',       fr: 'parcourir' },
        'upload.hint':          { en: 'Supports .xlsx, .xls, .xlsm, .csv — Max 100 MB per file', fr: '.xlsx, .xls, .xlsm, .csv — Max 100 Mo par fichier' },
        'upload.title':         { en: 'Uploaded Files',        fr: 'Fichiers Importés' },
        'upload.empty':         { en: 'No files uploaded',     fr: 'Aucun fichier importé' },
        'btn.clear_all':        { en: '✗ Clear All',           fr: '✗ Tout Supprimer' },

        // ── Output pages ───────────────────────────────────────
        'out.dc.title':         { en: 'Daily Concession (DC)', fr: 'Concession Journalière (DC)' },
        'out.dw.title':         { en: 'Daily Well (DW)',       fr: 'Puits Journalier (DW)' },
        'out.mc.title':         { en: 'Monthly Concession (MC)',fr:'Concession Mensuelle (MC)' },
        'out.wt.title':         { en: 'Well Test (WT)',        fr: 'Test de Puits (WT)' },
        'out.dc.empty':         { en: 'No DC data. Run a daily extraction first.', fr: 'Aucune donnée DC. Lancez une extraction journalière.' },
        'out.dw.empty':         { en: 'No DW data. Run a daily extraction first.', fr: 'Aucune donnée DW. Lancez une extraction journalière.' },
        'out.mc.empty':         { en: 'No MC data. Run a monthly extraction first.',fr:'Aucune donnée MC. Lancez une extraction mensuelle.' },
        'out.wt.empty':         { en: 'No Well Test data. Run a well test extraction first.',fr:'Aucune donnée WT. Lancez une extraction test de puits.' },
        'btn.export_dc':        { en: '📤 Export DC',           fr: '📤 Exporter DC' },
        'btn.export_dw':        { en: '📤 Export DW',           fr: '📤 Exporter DW' },
        'btn.export_mc':        { en: '📤 Export MC',           fr: '📤 Exporter MC' },
        'btn.export_wt':        { en: '📤 Export WT',           fr: '📤 Exporter WT' },

        // ── Logs page ──────────────────────────────────────────

        'logs.title':           { en: 'Application Logs',      fr: 'Journaux de l\'Application' },
        'btn.clear':            { en: 'Clear',                 fr: 'Effacer' },

        // ── Status values ──────────────────────────────────────
        'status.loaded':        { en: 'Loaded',                fr: 'Chargée' },
        'status.not_loaded':    { en: 'Not loaded',            fr: 'Non chargée' },

        // ── Toasts ─────────────────────────────────────────────
        'toast.paths_saved':    { en: 'Paths saved successfully',    fr: 'Chemins sauvegardés' },
        'toast.extract_first':  { en: 'Run an extraction first',     fr: 'Lancez une extraction d\'abord' },
        'toast.upload_failed':  { en: 'Upload failed',               fr: 'Échec de l\'import' },
        'toast.network_error':  { en: 'Network error',               fr: 'Erreur réseau' },
        'toast.prepare_files':  { en: 'Preparing files...',          fr: 'Préparation des fichiers...' },
        'toast.cleared':        { en: 'Data cleared',                fr: 'Données effacées' },

        // ── Page titles ────────────────────────────────────────
        'page.dashboard':       { en: 'Dashboard',             fr: 'Tableau de Bord' },
        'page.extract':         { en: 'Extract & Process',     fr: 'Extraction & Traitement' },
        'page.upload':          { en: 'Upload Files',          fr: 'Importer des Fichiers' },
        'page.output-dc':       { en: 'Daily Concession (DC)', fr: 'Concession Journalière (DC)' },
        'page.output-dw':       { en: 'Daily Well (DW)',       fr: 'Puits Journalier (DW)' },
        'page.output-mc':       { en: 'Monthly Concession (MC)',fr:'Concession Mensuelle (MC)' },
        'page.well-test':       { en: 'Well Test (WT)',        fr: 'Test de Puits (WT)' },

        'page.logs':            { en: 'Application Logs',      fr: 'Journaux' },

        // ── Auth ───────────────────────────────────────────────
        'auth.login.title':     { en: 'Welcome back',          fr: 'Bon retour' },
        'auth.login.subtitle':  { en: 'Sign in to your account to continue', fr: 'Connectez-vous à votre compte pour continuer' },
        'auth.login.email':     { en: 'Email Address',         fr: 'Adresse Email' },
        'auth.login.password':  { en: 'Password',              fr: 'Mot de passe' },
        'auth.login.remember':  { en: 'Remember me',           fr: 'Se souvenir de moi' },
        'auth.login.forgot':    { en: 'Forgot password?',      fr: 'Mot de passe oublié ?' },
        'auth.login.btn':       { en: 'Sign In',               fr: 'Se Connecter' },
        'auth.login.footer1':   { en: 'Don\'t have an account?', fr: 'Vous n\'avez pas de compte ?' },
        'auth.login.footer2':   { en: 'Sign up',               fr: 'S\'inscrire' },

        'auth.register.title':  { en: 'Create your account',   fr: 'Créer votre compte' },
        'auth.register.subtitle':{ en: 'Get started with DPR Manager in minutes', fr: 'Démarrez avec DPR Manager en quelques minutes' },
        'auth.register.name':   { en: 'Full Name',             fr: 'Nom Complet' },
        'auth.register.role':   { en: 'Role',                  fr: 'Rôle' },
        'auth.register.role.op':{ en: 'Operator',              fr: 'Opérateur' },
        'auth.register.role.eng':{ en: 'Engineer',             fr: 'Ingénieur' },
        'auth.register.role.mgr':{ en: 'Manager',              fr: 'Manager' },
        'auth.register.role.adm':{ en: 'Administrator',        fr: 'Administrateur' },
        'auth.register.company':{ en: 'Company / Organization',fr: 'Entreprise / Organisation' },
        'auth.register.pwd':    { en: 'Password',              fr: 'Mot de passe' },
        'auth.register.pwd_ph': { en: 'Create a secure password', fr: 'Créez un mot de passe sécurisé' },
        'auth.register.confirm':{ en: 'Confirm Password',      fr: 'Confirmer le mot de passe' },
        'auth.register.terms':  { en: 'I agree to the',        fr: 'J\'accepte les' },
        'auth.register.tos':    { en: 'Terms of Service',      fr: 'Conditions d\'Utilisation' },
        'auth.register.and':    { en: 'and',                   fr: 'et' },
        'auth.register.privacy':{ en: 'Privacy Policy',        fr: 'Politique de Confidentialité' },
        'auth.register.btn':    { en: 'Create Account',        fr: 'Créer le Compte' },
        'auth.register.footer1':{ en: 'Already have an account?', fr: 'Vous avez déjà un compte ?' },
        'auth.register.footer2':{ en: 'Sign in',               fr: 'Se connecter' },
        'auth.logout':          { en: '⎋ Logout',              fr: '⎋ Se déconnecter' },
        
        'auth.illus.title1':    { en: 'Industrial Production', fr: 'Production Industrielle' },
        'auth.illus.title2':    { en: 'Analytics Hub',         fr: 'Centre d\'Analyses' },
        'auth.illus.f1':        { en: 'Automated Daily Reporting', fr: 'Reporting Journalier Automatisé' },
        'auth.illus.f2':        { en: 'Secure Concession Management', fr: 'Gestion Sécurisée des Concessions' },
        'auth.illus.f3':        { en: 'Real-time Extraction Engine', fr: 'Moteur d\'Extraction en Temps Réel' },
        
        'auth.illus.r_title1':  { en: 'Join the Future of',    fr: 'Rejoignez le Futur de' },
        'auth.illus.r_title2':  { en: 'Data Management',       fr: 'la Gestion de Données' },
        'auth.illus.r_f1':      { en: 'Fast & Reliable Extractions', fr: 'Extractions Rapides et Fiables' },
        'auth.illus.r_f2':      { en: 'Advanced Analytical Dashboards', fr: 'Tableaux de Bord Analytiques Avancés' },
        'auth.illus.r_f3':      { en: 'Enterprise-Grade Security', fr: 'Sécurité de Niveau Entreprise' },
        
        // ── User Management (Admin Only) ───────────────────────
        'section.admin':        { en: 'Administration',        fr: 'Administration' },
        'nav.users':            { en: 'User Management',       fr: 'Gestion Utilisateurs' },
        'page.users':           { en: 'User Management',       fr: 'Gestion des Utilisateurs' },
        'users.total_accounts': { en: 'Total Accounts',        fr: 'Total des Comptes' },
        'users.admins':         { en: 'Administrators',        fr: 'Administrateurs' },
        'users.operators':      { en: 'Operators / Engineers', fr: 'Opérateurs / Ingénieurs' },
        'users.add_user':       { en: 'Add User',              fr: 'Ajouter Utilisateur' },
        'users.search_placeholder': { en: 'Search users by name, email, company...', fr: 'Rechercher par nom, email, entreprise...' },
        'users.table.name':     { en: 'User Details',          fr: 'Détails de l\'Utilisateur' },
        'users.table.company':  { en: 'Company',               fr: 'Entreprise' },
        'users.table.role':     { en: 'Role',                  fr: 'Rôle' },
        'users.table.created':  { en: 'Created At',            fr: 'Créé le' },
        'users.table.actions':  { en: 'Actions',               fr: 'Actions' },
        'users.role.admin':     { en: 'Admin',                 fr: 'Admin' },
        'users.role.user':      { en: 'Operator',              fr: 'Opérateur' },
        'users.action.edit_role': { en: 'Change Role',         fr: 'Changer le Rôle' },
        'users.action.reset_pwd': { en: 'Reset Password',      fr: 'Réinitialiser MDP' },
        'users.action.delete':  { en: 'Delete Account',        fr: 'Supprimer le Compte' },
        'users.modal.add.title': { en: 'Create New Account',    fr: 'Créer un Nouveau Compte' },
        'users.modal.edit.title': { en: 'Change Account Role',  fr: 'Modifier le Rôle' },
        'users.modal.reset.title': { en: 'Reset Password',     fr: 'Réinitialiser le Mot de Passe' },
        'users.form.fullname':  { en: 'Full Name',             fr: 'Nom Complet' },
        'users.form.email':     { en: 'Email Address',         fr: 'Adresse Email' },
        'users.form.company':   { en: 'Company / Organization', fr: 'Entreprise / Organisation' },
        'users.form.password':  { en: 'Initial Password',      fr: 'Mot de Passe Initial' },
        'users.form.role':      { en: 'Assigned Role',         fr: 'Rôle Attribué' },
        'users.btn.create':     { en: 'Create Account',        fr: 'Créer le Compte' },
        'users.btn.cancel':     { en: 'Cancel',                fr: 'Annuler' },
        'users.btn.save':       { en: 'Save Changes',          fr: 'Enregistrer' },
        'users.toast.created':  { en: 'User account created successfully.', fr: 'Compte utilisateur créé avec succès.' },
        'users.toast.role_updated': { en: 'User role updated successfully.', fr: 'Rôle de l\'utilisateur mis à jour.' },
        'users.toast.pwd_reset': { en: 'Password reset successfully. Active sessions terminated.', fr: 'Mot de passe réinitialisé. Sessions terminées.' },
        'users.toast.deleted':  { en: 'User account deleted successfully.', fr: 'Compte utilisateur supprimé.' },
        'users.confirm.delete': { en: 'Are you sure you want to delete this user account? Active sessions will be terminated.', fr: 'Êtes-vous sûr de vouloir supprimer ce compte ? Les sessions actives seront terminées.' },
    };

    let currentLang = localStorage.getItem('dpr_lang') || 'en';

    /** Get a translated string. Falls back to English then to the key. */
    function t(key) {
        const entry = translations[key];
        if (!entry) return key;
        return entry[currentLang] || entry.en || key;
    }

    /** Apply translations to all elements with data-i18n attribute. */
    function apply() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const text = t(key);

            // Handle different element types
            if (el.tagName === 'INPUT' && el.type !== 'checkbox') {
                el.placeholder = text;
            } else if (el.tagName === 'OPTION') {
                el.textContent = text;
            } else {
                el.textContent = text;
            }
        });

        // Update <html lang>
        document.documentElement.lang = currentLang;

        // Update toggle button label
        const toggle = document.getElementById('lang-toggle');
        if (toggle) toggle.textContent = currentLang === 'en' ? 'FR' : 'EN';
    }

    /** Switch language. */
    function set(lang) {
        currentLang = lang;
        localStorage.setItem('dpr_lang', lang);
        apply();
    }

    /** Toggle between EN and FR. */
    function toggle() {
        set(currentLang === 'en' ? 'fr' : 'en');
    }

    /** Get current language code. */
    function lang() { return currentLang; }

    return { t, apply, set, toggle, lang };
})();
