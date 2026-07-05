# Dashboard kursów walut NBP

Projekt zaliczeniowy z przedmiotu **Zarządzanie Big Data**.

Aplikacja jest interaktywnym dashboardem w Streamlit, który analizuje historyczne kursy walut publikowane przez Narodowy Bank Polski.

## Link do aplikacji

Po wdrożeniu na Streamlit Community Cloud wklej tutaj link:

```text
https://twoja-aplikacja.streamlit.app
```

## Źródło danych

Dane są pobierane z publicznego API NBP:

- tabela A kursów średnich walut obcych,
- historyczne kursy walut,
- opcjonalnie ceny złota.

API nie wymaga klucza ani płatnego konta.

## Co robi aplikacja

Dashboard umożliwia:

- wybór walut do analizy,
- wybór liczby ostatnich notowań,
- filtrowanie zakresu dat,
- opcjonalne dodanie ceny złota,
- analizę trendów kursów,
- porównanie zmian procentowych,
- analizę zmienności,
- analizę korelacji między walutami,
- pobranie oczyszczonych danych jako CSV.

## Spełnienie wymagań projektu

Projekt spełnia wymagania techniczne:

- prawdziwe źródło danych: publiczne API NBP,
- czyszczenie i przygotowanie danych,
- analiza i EDA,
- minimum 5 typów wykresów:
  - liniowy,
  - słupkowy,
  - histogram,
  - boxplot,
  - scatter plot,
  - heatmapa,
- minimum 3 widgety filtrujące:
  - multiselect,
  - slider,
  - date input,
  - checkbox,
- przemyślany layout:
  - sidebar,
  - KPI w kolumnach,
  - zakładki tematyczne,
- gotowy kod do deploymentu na Streamlit Community Cloud.

## Jak uruchomić lokalnie

1. Sklonuj repozytorium:

```bash
git clone https://github.com/TWOJ_LOGIN/TWOJE_REPO.git
cd TWOJE_REPO
```

2. Utwórz środowisko i zainstaluj zależności:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Instalacja pakietów:

```bash
pip install -r requirements.txt
```

3. Uruchom aplikację:

```bash
streamlit run app.py
```

## Deployment na Streamlit Community Cloud

1. Wrzuć pliki projektu na publiczne repozytorium GitHub.
2. Wejdź na https://share.streamlit.io.
3. Zaloguj się kontem GitHub.
4. Kliknij **New app**.
5. Wybierz:
   - repository: swoje repo,
   - branch: `main`,
   - main file path: `app.py`.
6. Kliknij **Deploy**.
7. Po wdrożeniu skopiuj link do aplikacji i wklej go w Moodle razem z linkiem do repozytorium.

## Struktura plików

```text
.
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
└── .streamlit/
    └── config.toml
```

## Autor

Kacper Kołodziejczyk
