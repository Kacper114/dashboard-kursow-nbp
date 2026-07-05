import datetime as dt
from typing import Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st


NBP_API_BASE = "https://api.nbp.pl/api"


st.set_page_config(
    page_title="Dashboard kursów walut NBP",
    page_icon="💱",
    layout="wide",
)


# -------------------------------------------------------------------
# Pobieranie danych
# -------------------------------------------------------------------
def request_json(url: str) -> dict | list:
    """Wysyła zapytanie do API NBP i zwraca odpowiedź JSON."""
    response = requests.get(
        url,
        headers={"Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=60 * 60)
def load_current_currency_table() -> pd.DataFrame:
    """Pobiera aktualną tabelę A kursów średnich NBP."""
    url = f"{NBP_API_BASE}/exchangerates/tables/A/?format=json"
    payload = request_json(url)[0]

    df = pd.DataFrame(payload["rates"])
    df["effective_date"] = pd.to_datetime(payload["effectiveDate"])
    df["table_no"] = payload["no"]
    df = df.rename(
        columns={
            "currency": "currency_name",
            "code": "currency_code",
            "mid": "rate_pln",
        }
    )

    return df[["effective_date", "table_no", "currency_name", "currency_code", "rate_pln"]]


@st.cache_data(ttl=60 * 60)
def load_currency_history(currency_code: str, last_quotations: int) -> pd.DataFrame:
    """Pobiera historię kursu jednej waluty z tabeli A NBP."""
    url = (
        f"{NBP_API_BASE}/exchangerates/rates/A/"
        f"{currency_code}/last/{last_quotations}/?format=json"
    )
    payload = request_json(url)

    df = pd.DataFrame(payload["rates"])
    df["currency_code"] = payload["code"]
    df["currency_name"] = payload["currency"]
    df = df.rename(columns={"effectiveDate": "date", "mid": "rate_pln"})
    df["date"] = pd.to_datetime(df["date"])
    df["rate_pln"] = pd.to_numeric(df["rate_pln"], errors="coerce")

    return df[["date", "currency_name", "currency_code", "rate_pln", "no"]]


@st.cache_data(ttl=60 * 60)
def load_gold_history(last_quotations: int) -> pd.DataFrame:
    """Pobiera historię ceny złota z NBP jako dodatkową serię porównawczą."""
    url = f"{NBP_API_BASE}/cenyzlota/last/{last_quotations}/?format=json"
    payload = request_json(url)

    df = pd.DataFrame(payload)
    df = df.rename(columns={"data": "date", "cena": "rate_pln"})
    df["date"] = pd.to_datetime(df["date"])
    df["currency_code"] = "XAU"
    df["currency_name"] = "złoto, cena 1 g w PLN"
    df["no"] = np.nan
    df["rate_pln"] = pd.to_numeric(df["rate_pln"], errors="coerce")

    return df[["date", "currency_name", "currency_code", "rate_pln", "no"]]


def load_many_histories(
    currency_codes: Iterable[str],
    last_quotations: int,
    include_gold: bool,
) -> pd.DataFrame:
    """Pobiera dane dla wielu walut i łączy je w jedną tabelę."""
    frames = []

    for code in currency_codes:
        try:
            frames.append(load_currency_history(code, last_quotations))
        except requests.HTTPError:
            st.warning(f"Nie udało się pobrać danych dla waluty: {code}")

    if include_gold:
        try:
            frames.append(load_gold_history(last_quotations))
        except requests.HTTPError:
            st.warning("Nie udało się pobrać danych o cenie złota.")

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


# -------------------------------------------------------------------
# Czyszczenie i przygotowanie danych
# -------------------------------------------------------------------
def clean_and_prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    """Czyści dane i dodaje kolumny analityczne."""
    if df.empty:
        return df

    prepared = df.copy()

    prepared = prepared.drop_duplicates(subset=["date", "currency_code"])
    prepared = prepared.dropna(subset=["date", "currency_code", "rate_pln"])
    prepared["rate_pln"] = pd.to_numeric(prepared["rate_pln"], errors="coerce")
    prepared = prepared.dropna(subset=["rate_pln"])

    prepared = prepared.sort_values(["currency_code", "date"])

    prepared["daily_change_pln"] = prepared.groupby("currency_code")["rate_pln"].diff()
    prepared["daily_return_pct"] = (
        prepared.groupby("currency_code")["rate_pln"].pct_change() * 100
    )

    first_value = prepared.groupby("currency_code")["rate_pln"].transform("first")
    prepared["indexed_100"] = prepared["rate_pln"] / first_value * 100

    prepared["rolling_7"] = (
        prepared.groupby("currency_code")["rate_pln"]
        .transform(lambda series: series.rolling(window=7, min_periods=1).mean())
    )

    prepared["year"] = prepared["date"].dt.year
    prepared["month"] = prepared["date"].dt.to_period("M").astype(str)
    prepared["day_of_week"] = prepared["date"].dt.day_name()

    return prepared


def build_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    """Tworzy tabelę podsumowującą dla wybranych walut."""
    summary = (
        df.groupby("currency_code")
        .agg(
            currency_name=("currency_name", "first"),
            observations=("rate_pln", "count"),
            first_date=("date", "min"),
            last_date=("date", "max"),
            first_rate=("rate_pln", "first"),
            last_rate=("rate_pln", "last"),
            min_rate=("rate_pln", "min"),
            max_rate=("rate_pln", "max"),
            mean_rate=("rate_pln", "mean"),
            volatility_pct=("daily_return_pct", "std"),
        )
        .reset_index()
    )

    summary["period_change_pct"] = (
        (summary["last_rate"] / summary["first_rate"] - 1) * 100
    )
    summary["range_pln"] = summary["max_rate"] - summary["min_rate"]

    return summary.sort_values("period_change_pct", ascending=False)


def format_pct(value: float) -> str:
    if pd.isna(value):
        return "brak danych"
    return f"{value:.2f}%"


def format_pln(value: float) -> str:
    if pd.isna(value):
        return "brak danych"
    return f"{value:,.4f} PLN".replace(",", " ")


# -------------------------------------------------------------------
# Interfejs aplikacji
# -------------------------------------------------------------------
st.title("💱 Dashboard kursów walut NBP")
st.markdown(
    """
Aplikacja analizuje historyczne kursy średnie walut publikowane przez Narodowy Bank Polski.
Dane są pobierane z publicznego API NBP, czyszczone, przeliczane i prezentowane jako interaktywny dashboard.
"""
)

try:
    current_table = load_current_currency_table()
except Exception as error:
    st.error("Nie udało się pobrać aktualnej tabeli kursów z API NBP.")
    st.exception(error)
    st.stop()

available_codes = sorted(current_table["currency_code"].unique())
default_codes = [code for code in ["EUR", "USD", "CHF", "GBP"] if code in available_codes]

with st.sidebar:
    st.header("Filtry")

    selected_codes = st.multiselect(
        "Wybierz waluty",
        options=available_codes,
        default=default_codes,
        help="Wybierz od 1 do 8 walut. Większa liczba walut może spowolnić pobieranie danych.",
    )

    if len(selected_codes) > 8:
        st.warning("Dla czytelności ograniczam analizę do pierwszych 8 wybranych walut.")
        selected_codes = selected_codes[:8]

    last_quotations = st.slider(
        "Liczba ostatnich notowań",
        min_value=30,
        max_value=255,
        value=180,
        step=15,
    )

    include_gold = st.checkbox(
        "Dodaj cenę złota jako serię XAU",
        value=False,
        help="Cena 1 g złota w PLN z API NBP. To dodatkowa seria porównawcza.",
    )

    show_rolling_average = st.checkbox(
        "Pokaż 7-okresową średnią kroczącą",
        value=True,
    )

    st.divider()
    st.caption("Źródło danych: publiczne API NBP.")

if not selected_codes and not include_gold:
    st.info("Wybierz co najmniej jedną walutę albo zaznacz cenę złota.")
    st.stop()

with st.spinner("Pobieram i przygotowuję dane z API NBP..."):
    raw_data = load_many_histories(selected_codes, last_quotations, include_gold)
    data = clean_and_prepare_data(raw_data)

if data.empty:
    st.error("Brak danych do analizy po zastosowaniu filtrów.")
    st.stop()

min_date = data["date"].min().date()
max_date = data["date"].max().date()

with st.sidebar:
    selected_date_range = st.date_input(
        "Zakres dat",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
    start_date, end_date = selected_date_range
else:
    start_date, end_date = min_date, max_date

filtered = data[
    (data["date"].dt.date >= start_date)
    & (data["date"].dt.date <= end_date)
].copy()

if filtered.empty:
    st.warning("Po wybraniu zakresu dat nie ma danych do pokazania.")
    st.stop()

summary = build_summary_table(filtered)
latest_rows = (
    filtered.sort_values("date")
    .groupby("currency_code")
    .tail(1)
    .sort_values("currency_code")
)


# -------------------------------------------------------------------
# KPI
# -------------------------------------------------------------------
st.subheader("Najważniejsze wskaźniki")

kpi_1, kpi_2, kpi_3, kpi_4 = st.columns(4)

with kpi_1:
    st.metric("Liczba serii", filtered["currency_code"].nunique())

with kpi_2:
    st.metric("Liczba obserwacji", f"{len(filtered):,}".replace(",", " "))

with kpi_3:
    top_change = summary.iloc[0]
    st.metric(
        "Największy wzrost w okresie",
        top_change["currency_code"],
        format_pct(top_change["period_change_pct"]),
    )

with kpi_4:
    top_volatility = summary.sort_values("volatility_pct", ascending=False).iloc[0]
    st.metric(
        "Największa zmienność dzienna",
        top_volatility["currency_code"],
        format_pct(top_volatility["volatility_pct"]),
    )


# -------------------------------------------------------------------
# Zakładki
# -------------------------------------------------------------------
tab_trends, tab_volatility, tab_relations, tab_data, tab_about = st.tabs(
    [
        "📈 Trendy i KPI",
        "📊 Zmienność",
        "🔍 Porównania",
        "🧾 Dane",
        "ℹ️ O projekcie",
    ]
)


with tab_trends:
    st.subheader("Kursy walut w czasie")

    fig_line = px.line(
        filtered,
        x="date",
        y="rate_pln",
        color="currency_code",
        hover_data=["currency_name"],
        title="Kurs średni NBP w PLN",
        labels={
            "date": "Data",
            "rate_pln": "Kurs w PLN",
            "currency_code": "Waluta",
            "currency_name": "Nazwa waluty",
        },
    )
    fig_line.update_layout(legend_title_text="Waluta")
    st.plotly_chart(fig_line, use_container_width=True)

    st.info(
        "Wykres pokazuje nominalny kurs średni NBP. Dla walut o różnych poziomach kursu "
        "lepsze jest porównanie indeksowane do 100."
    )

    fig_index = px.line(
        filtered,
        x="date",
        y="indexed_100",
        color="currency_code",
        title="Porównanie zmian kursów — indeks 100 na początku wybranego okresu",
        labels={
            "date": "Data",
            "indexed_100": "Indeks, pierwszy dzień = 100",
            "currency_code": "Waluta",
        },
    )
    fig_index.add_hline(y=100, line_dash="dash")
    st.plotly_chart(fig_index, use_container_width=True)

    if show_rolling_average:
        fig_rolling = px.line(
            filtered,
            x="date",
            y="rolling_7",
            color="currency_code",
            title="7-okresowa średnia krocząca kursu",
            labels={
                "date": "Data",
                "rolling_7": "Średnia krocząca kursu",
                "currency_code": "Waluta",
            },
        )
        st.plotly_chart(fig_rolling, use_container_width=True)

    col_a, col_b = st.columns(2)

    with col_a:
        fig_latest = px.bar(
            latest_rows.sort_values("rate_pln", ascending=False),
            x="currency_code",
            y="rate_pln",
            color="currency_code",
            title="Ostatni dostępny kurs według waluty",
            labels={
                "currency_code": "Waluta",
                "rate_pln": "Kurs w PLN",
            },
        )
        st.plotly_chart(fig_latest, use_container_width=True)

    with col_b:
        fig_change = px.bar(
            summary.sort_values("period_change_pct", ascending=False),
            x="currency_code",
            y="period_change_pct",
            color="period_change_pct",
            title="Zmiana procentowa w wybranym okresie",
            labels={
                "currency_code": "Waluta",
                "period_change_pct": "Zmiana [%]",
            },
        )
        fig_change.add_hline(y=0, line_dash="dash")
        st.plotly_chart(fig_change, use_container_width=True)


with tab_volatility:
    st.subheader("Analiza zmienności")

    returns = filtered.dropna(subset=["daily_return_pct"]).copy()

    col_a, col_b = st.columns(2)

    with col_a:
        fig_hist = px.histogram(
            returns,
            x="daily_return_pct",
            color="currency_code",
            nbins=40,
            barmode="overlay",
            title="Rozkład dziennych zmian procentowych",
            labels={
                "daily_return_pct": "Dzienna zmiana [%]",
                "currency_code": "Waluta",
            },
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_b:
        fig_box = px.box(
            returns,
            x="currency_code",
            y="daily_return_pct",
            color="currency_code",
            points="outliers",
            title="Boxplot dziennych zmian procentowych",
            labels={
                "currency_code": "Waluta",
                "daily_return_pct": "Dzienna zmiana [%]",
            },
        )
        st.plotly_chart(fig_box, use_container_width=True)

    st.info(
        "Histogram i boxplot pomagają ocenić, które waluty były bardziej stabilne, "
        "a które częściej miały większe dzienne wahania."
    )

    fig_range = px.bar(
        summary.sort_values("range_pln", ascending=False),
        x="currency_code",
        y="range_pln",
        color="currency_code",
        title="Zakres wahań kursu w PLN w wybranym okresie",
        labels={
            "currency_code": "Waluta",
            "range_pln": "Maksimum - minimum [PLN]",
        },
    )
    st.plotly_chart(fig_range, use_container_width=True)


with tab_relations:
    st.subheader("Porównania między walutami")

    fig_scatter = px.scatter(
        summary,
        x="volatility_pct",
        y="period_change_pct",
        size="observations",
        text="currency_code",
        hover_data=["currency_name", "first_rate", "last_rate", "min_rate", "max_rate"],
        title="Ryzyko i zmiana kursu: zmienność dzienna vs zmiana w okresie",
        labels={
            "volatility_pct": "Zmienność dzienna, odchylenie standardowe [%]",
            "period_change_pct": "Zmiana w okresie [%]",
            "observations": "Liczba obserwacji",
        },
    )
    fig_scatter.update_traces(textposition="top center")
    fig_scatter.add_hline(y=0, line_dash="dash")
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.info(
        "Wykres punktowy pokazuje relację między zmianą kursu w okresie a zmiennością. "
        "Waluty w prawym górnym rogu jednocześnie rosły i miały większe wahania."
    )

    pivot_returns = (
        filtered.pivot_table(
            index="date",
            columns="currency_code",
            values="daily_return_pct",
            aggfunc="mean",
        )
        .dropna(how="all")
    )

    if pivot_returns.shape[1] >= 2:
        corr = pivot_returns.corr()
        fig_heatmap = px.imshow(
            corr,
            text_auto=".2f",
            aspect="auto",
            title="Macierz korelacji dziennych zmian procentowych",
            labels={"color": "Korelacja"},
        )
        st.plotly_chart(fig_heatmap, use_container_width=True)
    else:
        st.warning("Do macierzy korelacji wybierz co najmniej dwie serie.")

    monthly = (
        filtered.groupby(["month", "currency_code"], as_index=False)["daily_return_pct"]
        .mean()
        .dropna()
    )

    fig_month = px.bar(
        monthly,
        x="month",
        y="daily_return_pct",
        color="currency_code",
        barmode="group",
        title="Średnia dzienna zmiana procentowa według miesiąca",
        labels={
            "month": "Miesiąc",
            "daily_return_pct": "Średnia dzienna zmiana [%]",
            "currency_code": "Waluta",
        },
    )
    fig_month.add_hline(y=0, line_dash="dash")
    st.plotly_chart(fig_month, use_container_width=True)


with tab_data:
    st.subheader("Tabela danych po czyszczeniu")

    st.dataframe(
        filtered.sort_values(["currency_code", "date"], ascending=[True, False]),
        use_container_width=True,
    )

    st.subheader("Podsumowanie walut")

    display_summary = summary.copy()
    numeric_columns = [
        "first_rate",
        "last_rate",
        "min_rate",
        "max_rate",
        "mean_rate",
        "volatility_pct",
        "period_change_pct",
        "range_pln",
    ]
    display_summary[numeric_columns] = display_summary[numeric_columns].round(4)

    st.dataframe(display_summary, use_container_width=True)

    csv_data = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Pobierz oczyszczone dane jako CSV",
        data=csv_data,
        file_name="oczyszczone_kursy_nbp.csv",
        mime="text/csv",
    )


with tab_about:
    st.subheader("Opis projektu")

    st.markdown(
        """
### Cel aplikacji

Celem aplikacji jest analiza kursów walut publikowanych przez Narodowy Bank Polski.
Dashboard pozwala porównywać waluty, sprawdzać trendy, zmienność i korelacje dziennych zmian.

### Źródło danych

Dane pochodzą z publicznego API NBP:

- tabela A kursów średnich walut obcych,
- historyczne notowania walut,
- opcjonalnie ceny złota.

### Czyszczenie i przygotowanie danych

W aplikacji wykonano następujące kroki:

1. pobranie danych JSON z API,
2. ujednolicenie nazw kolumn,
3. konwersję dat i kursów na odpowiednie typy,
4. usunięcie duplikatów i braków,
5. dodanie kolumn pochodnych:
   - dzienna zmiana w PLN,
   - dzienna zmiana procentowa,
   - indeks 100 dla porównywania walut,
   - 7-okresowa średnia krocząca,
   - miesiąc, rok i dzień tygodnia.

### Typy wykresów

Aplikacja zawiera więcej niż wymagane minimum 5 typów wykresów:

- wykres liniowy,
- wykres słupkowy,
- histogram,
- boxplot,
- scatter plot,
- heatmapę korelacji.

### Filtry i widgety

Dashboard zawiera minimum 3 widgety filtrujące:

- multiselect walut,
- slider liczby notowań,
- date input zakresu dat,
- checkbox ceny złota,
- checkbox średniej kroczącej.
"""
    )
