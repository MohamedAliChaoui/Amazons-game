# Guide de Déploiement : Démo Web du Jeu des Amazones

Cette démo a été spécialement conçue pour votre **portfolio**. Elle fait tourner le moteur Python complet (Bitboards & IA Minimax / MCTS) **directement dans le navigateur** via **WebAssembly (Pyodide)** sans nécessiter aucun serveur backend payant.

---

## 🚀 1. Tester la démo localement

Ouvrez un terminal PowerShell dans le dossier du projet :

```powershell
python -m http.server 8000 --directory web
```

Ouvrez ensuite votre navigateur à l'adresse : **[http://localhost:8000](http://localhost:8000)**.

---

## 🌐 2. Déploiement Gratuit sur GitHub Pages (Recommandé)

Grâce au fichier de workflow déjà configuré dans `.github/workflows/deploy.yml`, le déploiement sur GitHub Pages se fait automatiquement à chaque `git push`.

### Étapes :

1. **Initialiser Git et pousser sur GitHub** :
   ```powershell
   git init
   git add .
   git commit -m "feat: add interactive WebAssembly demo for portfolio"
   git branch -M main
   git remote add origin https://github.com/VOTRE_NOM_UTILISATEUR/amazons.git
   git push -u origin main
   ```

2. **Activer GitHub Pages dans votre dépôt** :
   * Allez sur votre dépôt GitHub : `Settings` > `Pages`.
   * Sous **Build and deployment** :
     * **Source** : Sélectionnez **GitHub Actions**.
   * Le déploiement se lance automatiquement ! Votre site sera accessible sur :
     `https://VOTRE_NOM_UTILISATEUR.github.io/amazons/`

---

## ⚡ 3. Déploiement en 1 Clic sur Vercel ou Netlify (Alternative)

Si votre portfolio est hébergé sur Vercel ou Netlify :

### Sur Vercel :
1. Connectez-vous sur [vercel.com](https://vercel.com).
2. Cliquez sur **Add New** > **Project** et sélectionnez votre dépôt `amazons`.
3. Dans **Root Directory**, cliquez sur **Edit** et sélectionnez le dossier `web`.
4. Cliquez sur **Deploy**. Votre démo est en ligne en 15 secondes avec une URL SSL personnalisée (ex: `amazons-demo.vercel.app`).

### Sur Netlify :
1. Glissez-déposez simplement le dossier `web/` sur [app.netlify.com/drop](https://app.netlify.com/drop).
2. Le site est immédiatement en ligne !

---

## 💼 4. Comment l'intégrer dans votre Portfolio

### Option A : Lien direct avec badge ou carte de projet
Dans votre page de projets ou CV en ligne :
```html
<a href="https://VOTRE_PSEUDO.github.io/amazons/" target="_blank" class="project-btn">
  🎮 Tester la Démo Live (WebAssembly)
</a>
```

### Option B : Iframe intégrée directement dans une page
Pour que le recruteur puisse jouer sans quitter votre site :
```html
<iframe 
  src="https://VOTRE_PSEUDO.github.io/amazons/" 
  width="100%" 
  height="850px" 
  style="border: none; border-radius: 16px; box-shadow: 0 8px 32px rgba(0,0,0,0.4);"
  title="Jeu des Amazones - Démo IA">
</iframe>
```

---

## 🎯 Ce que ce projet démontre aux recruteurs

1. **Maîtrise de l'Algorithmie & IA** : Minimax avec élagage $\alpha$-$\beta$, Monte Carlo Tree Search (UCT), heuristiques de territoire et mobilité.
2. **Optimisation Bas Niveau** : Bitboards en Python (manipulations de bits 64 bits rapides pour les règles et les calculs d'accessibilité).
3. **Architecture & Modernité** : Séparation MVC, tests `pytest`, conteneurisation WebAssembly (Pyodide), UI responsive en dark mode et Web Audio API.
