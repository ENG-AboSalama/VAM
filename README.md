<div align="center">
  <h1>🌟 VAM — Valorant Account Manager</h1>
  <img src="https://img.shields.io/badge/Platform-Windows-blue?style=for-the-badge" alt="Windows" />
  <img src="https://img.shields.io/badge/Language-Python%203.8%2B-yellow?style=for-the-badge&logo=python" alt="Python" />
  <img src="https://img.shields.io/badge/Game-Valorant-red?style=for-the-badge&logo=riotgames" alt="Valorant" />
  <p><strong>A modern CLI tool to manage multiple Valorant accounts faster and smarter.</strong></p>
</div>

---

## 🚀 About

**VAM (Valorant Account Manager)** is built for users who handle multiple Valorant accounts and need a fast workflow for:
- quick account switching/login,
- level progress tracking,
- FWOTD monitoring,
- and better day-to-day account management.

> ✅ Rebuilt from the ground up for better speed, cleaner UI, and smoother automation.

---

## ✨ Features

- **🎮 One-Click Auto Login**  
  Login/switch between accounts without manually typing credentials each time.

- **📈 Ranked-Ready Progress Tracking**  
  Track each account’s progress toward **Level 20**.

- **🎯 FWOTD Tracker**  
  Instantly see which accounts still need **First Win of the Day** bonus XP.

- **🛡️ Local Data Storage**  
  Account data is stored locally on your machine.

- **🖥️ Rich Interactive Terminal UI**  
  Clean and modern CLI dashboard powered by [`rich`](https://github.com/Textualize/rich).

- **⚡ Setup Wizard**  
  First launch includes automatic configuration guidance (Riot Client path detection, etc.).

---

## 📸 Preview

> Add screenshots/GIFs here for better presentation.

```text
assets/dashboard.png
assets/setup-wizard.png
assets/fwotd-view.png
```

Example:

```md
![Dashboard](assets/dashboard.png)
```

---

## 🛠️ Installation

### 1) Clone the repository

```bash
git clone https://github.com/ENG-AboSalama/VAM.git
cd VAM
```

### 2) Install dependencies

Make sure **Python 3.8+** is installed.

```bash
# Option A: using batch script
install.bat

# Option B: using pip
pip install -r requirements.txt
```

### 3) Run VAM

```bash
python main.py
```

On first run, the **Setup Wizard** will guide you automatically.

---

## ✅ Requirements

- **OS:** Windows
- **Python:** 3.8 or newer
- **Game:** Valorant installed
- Riot Client available on the same machine

---

## 🧠 Usage Tips

- Keep account names clear (e.g., `Acc-01`, `Acc-02`) for faster switching.
- Run VAM as a normal user unless admin permissions are explicitly required.
- Keep your Python dependencies updated for best stability.

---

## 🔒 Security & Privacy

- VAM stores account-related configuration **locally**.
- Never share your local config/data files publicly.
- This project is intended for **personal/educational use**.
- You are responsible for using the tool in compliance with Riot’s Terms of Service.

---

## 🧩 Troubleshooting

### Python not recognized
- Ensure Python is installed and added to `PATH`.
- Try:
  ```bash
  py --version
  ```

### Missing packages
- Reinstall dependencies:
  ```bash
  pip install -r requirements.txt --upgrade
  ```

### Riot Client path issues
- Re-run setup and manually verify client path if auto-detection fails.

---

## 🗺️ Roadmap

- [ ] Export/import accounts
- [ ] Optional encrypted local storage
- [ ] Session/time analytics improvements
- [ ] Multi-language support (EN/AR)

---

## 🤝 Contributing

Contributions are welcome!  
If you have ideas, open an issue or submit a pull request.

1. Fork the repo
2. Create a feature branch
3. Commit your changes
4. Open a PR

---

## 👤 Credits

- **Developer:** [NIR0](https://github.com/ENG-AboSalama)
- **Powered by:** CursedTools

---

## 📜 Disclaimer

This project is not affiliated with, maintained, authorized, endorsed, or sponsored by **Riot Games, Inc.** or any of its affiliates.  
Use at your own risk.

---

<div align="center">
  <em>Made with ❤️ for the Valorant community.</em>
</div>
