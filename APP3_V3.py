import streamlit as st
import pandas as pd
import plotly.express as px

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(layout="wide")
st.title("🧺 LAVANDERÍA #2 - ANÁLISIS DE LEAD TIME")

# ======================================================
# FUNCION DE CARGA
# ======================================================
def load_data(file):
    try:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip().str.upper()
        # Columnas mínimas
        required = ["CLIENTE", "COCHE", "FECHA INGRESO", "FECHA DE SALIDA"]
        for col in required:
            if col not in df.columns:
                st.error(f"Falta la columna: {col}")
                return pd.DataFrame()
        # Fechas
        df["FECHA INGRESO"] = pd.to_datetime(df["FECHA INGRESO"], errors="coerce")
        df["FECHA DE SALIDA"] = pd.to_datetime(df["FECHA DE SALIDA"], errors="coerce")
        # Lead Time
        if "LEAD TIME" not in df.columns:
            df["LEAD TIME"] = (df["FECHA DE SALIDA"] - df["FECHA INGRESO"]).dt.days
        # Clasificación Lead Time
        if "CLASIFICACION L.TIME" not in df.columns:
            df["CLASIFICACION L.TIME"] = "NORMAL"
        # Clasificación por lote
        if "LT" not in df.columns:
            df["LT"] = "SIN CLASIFICAR"
        df["LT"] = df["LT"].fillna("SIN CLASIFICAR")
        return df
    except Exception as e:
        st.error(f"Error cargando archivo: {e}")
        return pd.DataFrame()
    
#================================
#ESTANDARIZACION DE DATOS
#========================

    df.columns = df.columns.str.strip().str.upper().str.replace(" ", "_")
    sim_df.columns = sim_df.columns.str.strip().str.upper().str.replace(" ", "_")

# ======================================================
# SIDEBAR - SUBIR ARCHIVO Y FILTROS
# ======================================================
st.sidebar.header("Filtros")
archivo = st.sidebar.file_uploader("Subir Excel", type=["xlsx"])
df = pd.DataFrame()
if archivo:
    df = load_data(archivo)
else:
    st.info("Sube un archivo para comenzar")
    st.stop()

# ==========================
# FILTROS
# ==========================
# Cliente
clientes_sel = st.sidebar.multiselect(
    "Cliente",
    options=df["CLIENTE"].dropna().unique()
)

# Clasificación L.Time
clasif_sel = st.sidebar.multiselect(
    "Clasificación L.Time",
    options=df["CLASIFICACION L.TIME"].dropna().unique()
)

# Clasificación por Lote (LT) - considerar vacíos
lt_sel = st.sidebar.multiselect(
    "Clasificación por Lote (LT)",
    options=df["LT"].unique()
)

# Fechas
min_fecha = df["FECHA INGRESO"].min()
max_fecha = df["FECHA INGRESO"].max()
fecha_rango = st.sidebar.date_input(
    "Rango de fechas",
    value=(min_fecha, max_fecha)
)

# ==========================
# APLICAR FILTROS
# ==========================
df_f = df.copy()
if clientes_sel:
    df_f = df_f[df_f["CLIENTE"].isin(clientes_sel)]
if clasif_sel:
    df_f = df_f[df_f["CLASIFICACION L.TIME"].isin(clasif_sel)]
if lt_sel:
    df_f = df_f[df_f["LT"].isin(lt_sel)]
# Filtro de fechas
if isinstance(fecha_rango, tuple) and len(fecha_rango) == 2:
    inicio, fin = fecha_rango
    df_f = df_f[
        (df_f["FECHA INGRESO"] >= pd.to_datetime(inicio)) &
        (df_f["FECHA INGRESO"] <= pd.to_datetime(fin))
    ]

# ======================================================
# KPIs
# ======================================================
col1, col2, col3 = st.columns(3)
col1.metric("Total Registros", len(df_f))
col2.metric("Lead Time Promedio", round(df_f["LEAD TIME"].mean(), 2))
col3.metric("Clientes", df_f["CLIENTE"].nunique())

# ======================================================
# FLUJO ANIMADO
# ======================================================
st.subheader("🔄 Flujo Operacional (Coches, Lotes y Clientes)")
df_flujo = df_f.dropna(subset=["FECHA INGRESO", "FECHA DE SALIDA"])
if not df_flujo.empty:
    frames = []
    fechas = pd.date_range(df_flujo["FECHA INGRESO"].min(), df_flujo["FECHA DE SALIDA"].max(), freq="D")
    for fecha in fechas:
        temp = df_flujo.copy()
        # Estado: Entrada=0, WIP=1, Salida=2
        temp["X"] = 0
        temp.loc[temp["FECHA INGRESO"] <= fecha, "X"] = 1
        temp.loc[temp["FECHA DE SALIDA"] <= fecha, "X"] = 2
        temp["ESTADO"] = temp["X"].map({0:"Entrada",1:"WIP",2:"Salida"})
        temp["FRAME"] = fecha
        frames.append(temp)
    sim_df = pd.concat(frames)
    sim_df["FRAME_STR"] = sim_df["FRAME"].astype(str)
    columnas_hover = ["CLIENTE", "LT", "COCHE", "FECHA_INGRESO", "FECHA_DE_SALIDA", "ESTADO"]

    hover_data = {col: True for col in columnas_hover if col in sim_df.columns}

    fig_flujo = px.scatter(
        sim_df,
        x="X",
        y="COCHE",
        animation_frame="FRAME_STR",
        color="LT",
        size="LEAD TIME",
        text="LT",
        hover_data=hover_data,
)
    fig_flujo.update_traces(textposition="top center", marker=dict(opacity=0.8))
    fig_flujo.update_layout(
        xaxis=dict(
            tickvals=[0,1,2],
            ticktext=["Entrada","WIP","Salida"],
            title="Estado del Proceso"
        ),
        yaxis_title="Coche",
        legend_title="Lote (LT)",
        height=600
    )
    st.plotly_chart(fig_flujo, use_container_width=True)

    # Tabla Cliente → Lotes
    st.subheader("📦 Relación Cliente → Lotes")
    relacion = df_flujo.groupby("CLIENTE")["LT"].apply(lambda x: ', '.join(map(str, x.unique()))).reset_index()
    st.dataframe(relacion, use_container_width=True)

else:
    st.info("No hay datos para flujo")

# ======================================================
# BOX PLOT
# ======================================================
st.subheader("📊 Lead Time por Cliente")
if not df_f.empty:
    fig_box = px.box(df_f, x="CLIENTE", y="LEAD TIME", color="LT")
    st.plotly_chart(fig_box, use_container_width=True)
else:
    st.info("No hay datos para el boxplot")

# ======================================================
# GANTT
# ======================================================
st.subheader("📅 Gantt de Procesos")
if not df_flujo.empty:
    fig_gantt = px.timeline(
        df_flujo,
        x_start="FECHA INGRESO",
        x_end="FECHA DE SALIDA",
        y="COCHE",
        color="LT"
    )
    fig_gantt.update_yaxes(autorange="reversed")
    st.plotly_chart(fig_gantt, use_container_width=True)
else:
    st.info("No hay datos para Gantt")

# ======================================================
# TABLA COMPLETA
# ======================================================
st.subheader("📋 Datos")
st.dataframe(df_f, use_container_width=True)
