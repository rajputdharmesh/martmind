# 🛒 MartMind — Smart Grocery Spend Analyzer

A data analyst portfolio project that turns grocery bills into financial insights.

**Live demo:** [martmind.streamlit.app](https://martmind.streamlit.app)

## Features
- Upload CSV or PDF grocery bills
- Monthly spend tracking with charts
- Inflation tracker — see which items got more expensive
- Cheapest store finder based on your own purchase history
- Budget tracker with overspend alerts

## Tech Stack
`Python` · `SQLite` · `pandas` · `pdfplumber` · `Streamlit` · `Plotly`

## Run locally

```bash
git clone https://github.com/yourusername/martmind.git
cd martmind
pip install -r requirements.txt
streamlit run app.py
```

## Project Structure

```
martmind/
├── app.py                  ← Streamlit app (run this)
├── requirements.txt
├── .streamlit/
│   └── config.toml         ← Theme config
├── modules/
│   ├── database.py         ← SQLite schema
│   ├── parser.py           ← PDF & CSV extraction
│   ├── loader.py           ← DB insertion
│   └── analyzer.py         ← SQL analytics
└── sample_data/
    ├── sample_january.csv
    ├── sample_february.csv
    └── sample_march.csv
```
