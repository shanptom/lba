[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
# 🧪 Protocart — Protocol-to-Shopping List Agent



**Protocart** helps researchers turn lab protocols into actionable shopping lists. Upload your protocol, and the app will extract reagents, consumables, and small tools, then return direct product links from vendors like FisherSci, Sigma-Aldrich, and ThermoFisher.  

[![Streamlit App](https://img.shields.io/badge/Launch_App-Protocart-brightgreen?style=for-the-badge&logo=streamlit)](https://protocart.streamlit.app/)
---

## 🚀 Features

- 🧠 **AI-powered parsing** using Anthropic Claude
- 🛒 **Direct product links** from top lab vendors
- 📦 **Shopping checklist** with tracking and export to CSV
- 🔎 **Custom search** using catalog hints and specifications
- 💡 **Support for multiple vendors**: FisherSci, Sigma-Aldrich, ThermoFisher
- 📄 Example protocols and user guidance included

---

## 🖼️ Screenshot

![screenshot](/assets/screenshot.png) <!-- replace with actual path if needed -->

---

## 📂 How to Use

1. Go to [protocart.streamlit.app](https://protocart.streamlit.app/)
2. Upload a `.txt` protocol file
3. Choose a preferred vendor (e.g., `fishersci.com`)
4. Click "🔍 Find Products"
5. Browse links, check items added to cart, and download the list

---

## 🧰 Tech Stack

- [Streamlit](https://streamlit.io/)
- [Anthropic Claude 3.5 API](https://www.anthropic.com/)
- [BeautifulSoup4](https://pypi.org/project/beautifulsoup4/)
- [Requests](https://docs.python-requests.org/)
- [Pandas](https://pandas.pydata.org/)

---

## 🔒 Secrets (Required for Deployment)

Use `streamlit secrets` to provide your Claude API key:

[secrets.toml]

ANTHROPIC_API_KEY = "your_claude_api_key"

---

## 📦 Installation (Local)

```bash
git clone https://github.com/yourusername/protocart.git
cd protocart
pip install -r requirements.txt
streamlit run app.py
📜 License
This project is licensed under the MIT License.
