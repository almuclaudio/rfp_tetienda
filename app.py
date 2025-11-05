
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="TeTienda · Control y Métricas",
                   page_icon="🛍️",
                   layout="wide")

# ------ Branding ------
PRIMARY = "#0B63CE"
SUCCESS = "#2BB673"
WARNING = "#F2C037"
MUTED = "#607D8B"
LOGO_PATH = "logo_tetienda.png"

# ------ Column mapping (ajústalo si tu CSV real usa otros nombres) ------
COLS = dict(
    timestamp="fecha_interaccion",
    channel="canal",
    segment="pais",
    queue="cola",
    intent="motivo_consulta",
    resolved="resuelto_chatbot",
    handover="transferido_agente",
    fcr="fcr",
    response_time_sec="tiempo_respuesta_seg",
    aht_sec="aht_seg",
    csat="csat",
    nps="nps",
    returns_stage="funnel_devoluciones",
    session_id="id_sesion"
)

@st.cache_data
def load_data(path_or_buffer):
    df = pd.read_csv(path_or_buffer, parse_dates=[COLS["timestamp"]])
    # tipos
    for c in ["resolved","handover","fcr"]:
        if COLS[c] in df.columns:
            df[COLS[c]] = df[COLS[c]].astype(int)
    return df

from pathlib import Path

def header():
    cols = st.columns([1,4])
    with cols[0]:
        if Path(LOGO_PATH).exists():
            st.image(LOGO_PATH, width=140)
        else:
            st.markdown("""
                <div style='width:140px;height:80px;border:2px dashed #ccc;display:flex;align-items:center;justify-content:center;border-radius:8px;'>
                    <span style='color:#999;font-size:12px'>Sin logo</span>
                </div>
            """, unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"<h2 style='margin-bottom:0'>Dashboard de Control del Chatbot</h2>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:{MUTED};margin-top:4px'>Monitorización omnicanal: rendimiento, calidad y seguridad de la IA</p>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)


def sidebar(df):
    st.sidebar.header("Filtros")
    # SLA objetivo
    sla = st.sidebar.number_input("SLA de respuesta (seg)", min_value=1, max_value=120, value=20, step=1)
    min_d = df[COLS["timestamp"]].min().date()
    max_d = df[COLS["timestamp"]].max().date()
    dr = st.sidebar.date_input("Rango de fechas", (min_d, max_d), min_value=min_d, max_value=max_d)
    if isinstance(dr, tuple):
        start, end = dr
    else:
        start, end = dr, dr

    chs = ["Todos"] + sorted(df[COLS["channel"]].dropna().unique().tolist())
    segs = ["Todos"] + sorted(df[COLS["segment"]].dropna().unique().tolist())
    ints = ["Todos"] + sorted(df[COLS["intent"]].dropna().unique().tolist())

    # Cola es opcional
    queue_col = COLS.get("queue", None)
    has_queue = queue_col in df.columns if queue_col else False
    if has_queue:
        qs = ["Todos"] + sorted(df[queue_col].dropna().unique().tolist())
        qu = st.sidebar.selectbox("Cola", qs, index=0)
    else:
        qu = "Todos"

    ch = st.sidebar.selectbox("Canal", chs, index=0)
    sg = st.sidebar.selectbox("País", segs, index=0)
    it = st.sidebar.selectbox("Intención", ints, index=0)

    # Filtro de fechas robusto (Timestamp vs date)
    if isinstance(dr, tuple):
        start_ts, end_ts = [pd.to_datetime(d) for d in dr]
    else:
        start_ts, end_ts = pd.to_datetime(dr), pd.to_datetime(dr)

    f = df[(df[COLS['timestamp']] >= start_ts) & (df[COLS['timestamp']] <= (end_ts + pd.Timedelta(days=1)))]

    if ch != "Todos":
        f = f[f[COLS["channel"]] == ch]
    if sg != "Todos":
        f = f[f[COLS["segment"]] == sg]
    if it != "Todos":
        f = f[f[COLS["intent"]] == it]
    if has_queue and qu != "Todos":
        f = f[f[queue_col] == qu]

    return f, sla


def kpis(df, sla_sec):
    total = len(df)
    srr = df[COLS["resolved"]].mean()*100 if total and COLS["resolved"] in df else np.nan
    hov = df[COLS["handover"]].mean()*100 if total and COLS["handover"] in df else np.nan
    fcr = df[COLS["fcr"]].mean()*100 if total and COLS["fcr"] in df else np.nan
    csat = df[COLS["csat"]].mean() if COLS["csat"] in df else np.nan
    # NPS
    nps_series = df[COLS["nps"]].dropna()
    nps_score = np.nan
    if len(nps_series):
        promoters = (nps_series >= 9).mean()
        detractors = (nps_series <= 6).mean()
        nps_score = (promoters - detractors) * 100
    # SLA cumplimiento
    sla_ok = (df[COLS["response_time_sec"]] <= sla_sec).mean()*100 if total else np.nan

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Sesiones", f"{total:,}")
    c2.metric("SRR", f"{srr:.0f}%" if not np.isnan(srr) else "s/d")
    c3.metric("Handover", f"{hov:.0f}%" if not np.isnan(hov) else "s/d")
    c4.metric("FCR", f"{fcr:.0f}%" if not np.isnan(fcr) else "s/d")
    c5.metric("CSAT", f"{csat:.1f}/5" if not np.isnan(csat) else "s/d")
    c6.metric(f"SLA ≤ {sla_sec}s", f"{sla_ok:.0f}%" if not np.isnan(sla_ok) else "s/d")

def trends(df):
    st.subheader("Tendencias")
    daily = df.set_index(COLS["timestamp"]).resample("D").agg(
        sesiones=(COLS["session_id"], "count"),
        srr=(COLS["resolved"], "mean"),
        handover=(COLS["handover"], "mean")
    ).reset_index()
    fig1 = px.line(daily, x=COLS["timestamp"], y="sesiones", markers=True,
                   title="Volumen de sesiones por día",
                   color_discrete_sequence=[PRIMARY])
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.line(daily, x=COLS["timestamp"], y=["srr","handover"],
                   title="SRR y Handover (tendencia)",
                   labels={"value":"Ratio","variable":"Métrica","timestamp":"Fecha"},
                   color_discrete_sequence=[SUCCESS, WARNING])
    st.plotly_chart(fig2, use_container_width=True)

def breakdowns(df):
    st.subheader("Desglose por canal y país")
    # Por canal
    by_ch = df.groupby(COLS["channel"]).agg(
        sesiones=(COLS["session_id"], "count"),
        srr=(COLS["resolved"], "mean"),
        handover=(COLS["handover"], "mean")
    ).reset_index().sort_values("sesiones", ascending=False)
    fig3 = px.bar(by_ch, x=COLS["channel"], y="sesiones", title="Volumen por canal",
                  color_discrete_sequence=[PRIMARY])
    st.plotly_chart(fig3, use_container_width=True)
    fig31 = px.bar(by_ch, x=COLS["channel"], y=["srr","handover"], barmode="group",
                   title="SRR/Handover por canal",
                   labels={"value":"Ratio","variable":"Métrica"}, color_discrete_sequence=[SUCCESS, WARNING])
    st.plotly_chart(fig31, use_container_width=True)

    # Por país
    by_ct = df.groupby(COLS["segment"]).agg(
        sesiones=(COLS["session_id"], "count"),
        srr=(COLS["resolved"], "mean"),
        handover=(COLS["handover"], "mean")
    ).reset_index().sort_values("sesiones", ascending=False)
    fig4 = px.bar(by_ct, x=COLS["segment"], y="sesiones", title="Volumen por país",
                  color_discrete_sequence=[PRIMARY])
    st.plotly_chart(fig4, use_container_width=True)


def sla_by_queue(df, sla_sec):
    st.subheader("SLA por cola")
    queue_col = COLS.get("queue", None)
    if not queue_col or queue_col not in df.columns:
        st.info("Este dataset no incluye la columna de 'cola'. Se omite este bloque.")
        return
    agg = df.groupby(queue_col).agg(
        sesiones=(COLS["session_id"], "count"),
        sla_ok=(COLS["response_time_sec"], lambda s: (s <= sla_sec).mean())
    ).reset_index()
    agg["SLA_%"] = (agg["sla_ok"]*100).round(0)
    fig = px.bar(agg, x=queue_col, y="SLA_%", title=f"Cumplimiento SLA ≤ {sla_sec}s",
                 labels={"SLA_%":"Cumplimiento (%)"})
    st.plotly_chart(fig, use_container_width=True)


def returns_funnel(df):
    st.subheader("Embudo de devoluciones")
    stage_col = COLS["returns_stage"]
    if stage_col not in df.columns or df[stage_col].eq("").all():
        st.info("No hay datos de embudo de devoluciones en el dataset.")
        return
    order = ["Inicio","Verificación","Autorización","Recolección","Reembolso"]
    f = df[df[COLS["intent"]] == "Devoluciones"]
    counts = f[stage_col].value_counts().reindex(order).fillna(0).astype(int).reset_index()
    counts.columns = ["etapa","sesiones"]
    # funnel chart using bar with decreasing order
    fig = px.bar(counts, x="etapa", y="sesiones", title="Embudo de devoluciones",
                 color_discrete_sequence=[PRIMARY])
    st.plotly_chart(fig, use_container_width=True)

def top_blocks(df):
    st.subheader("Top problemas y oportunidades")
    # Top intenciones
    top_int = (df.groupby(COLS["intent"])[COLS["session_id"]]
               .count().sort_values(ascending=False).head(5).reset_index(name="sesiones"))
    fig1 = px.bar(top_int, x="sesiones", y=COLS["intent"], orientation="h",
                  title="Top 5 intenciones más frecuentes",
                  color_discrete_sequence=[PRIMARY])
    st.plotly_chart(fig1, use_container_width=True)

    # Mayor handover (mínimo N)
    stats = df.groupby(COLS["intent"]).agg(
        sesiones=(COLS["session_id"], "count"),
        handover_rate=(COLS["handover"], "mean")
    ).reset_index()
    stats = stats[stats["sesiones"] >= 60].sort_values("handover_rate", ascending=False).head(5)
    stats["handover_%"] = (stats["handover_rate"]*100).round(0)
    fig2 = px.bar(stats, x="handover_%", y=COLS["intent"], orientation="h",
                  title="Top 5 intenciones con mayor handover",
                  labels={"handover_%":"Handover (%)"},
                  color_discrete_sequence=[WARNING])
    st.plotly_chart(fig2, use_container_width=True)

def details(df):
    with st.expander("Detalle de sesiones (muestra)"):
        st.dataframe(df.sort_values(COLS["timestamp"], ascending=False).head(300))

def main():
    header()
    st.sidebar.write("Sube tu CSV o usa el ejemplo con branding.")
    mode = st.sidebar.selectbox("Origen de datos", ["Ejemplo con branding", "Subir CSV"])
    if mode == "Subir CSV":
        up = st.sidebar.file_uploader("CSV", type=["csv"])
        if up is None:
            st.stop()
        df = load_data(up)
    else:
        df = load_data("sample_tetienda.csv")

    fdf, sla_sec = sidebar(df)
    kpis(fdf, sla_sec)
    trends(fdf)
    breakdowns(fdf)
    sla_by_queue(fdf, sla_sec)
    returns_funnel(fdf)
    top_blocks(fdf)
    details(fdf)

    st.markdown("---")
    st.caption("Personaliza colores, logo y mapeo de columnas en la cabecera del archivo.")

if __name__ == "__main__":
    main()
